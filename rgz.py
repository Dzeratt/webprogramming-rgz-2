from flask import Blueprint, render_template, request, redirect, session, flash, Flask, request, jsonify, abort
import psycopg2
from werkzeug.security import check_password_hash, generate_password_hash
import math

rgz = Blueprint('rgz', __name__)

def dbConnect():
    conn = psycopg2.connect(
        host="127.0.0.1",
        database="Appliances",
        user="web_rgz",
        password="123")

    return conn;

def dbClose(cursor, connection):
    cursor.close()
    connection.close()


@rgz.route("/")
@rgz.route("/index/")
def main():
    user_id = session.get('id')
    username = session.get('username')

    if user_id is not None:
        return render_template('index.html', username=username)
    else:
        return redirect("/index/login")


@rgz.route('/index/register', methods = ["GET", "POST"])
def registerPage():

    visibleUser = session.get('username', 'Anonim')

    errors = []

    if request.method == "GET":
        return render_template('register.html', errors = errors, username = visibleUser)
    
    username = request.form.get("username")
    password = request.form.get("password")

    if not (username and password):
        errors.append('Пожалуйста заполните все поля')
        print(errors)
        return render_template('register.html', errors = errors)
    
    hashPassword = generate_password_hash(password)
    
    conn = dbConnect()
    cur = conn.cursor()

    cur.execute("SELECT username FROM users WHERE username = %s;", (username,))

    if cur.fetchone() is not None:
        errors.append("Пользователь с данным именем уже существует")

        dbClose(cur, conn)

        return render_template('register.html', errors=errors)
    
    cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s);", (username, hashPassword))

    conn.commit()
    dbClose(cur, conn)

    return redirect("/index/login")


@rgz.route('/index/login', methods=["GET", "POST"])
def loginPage():
    visibleUser = session.get('username', 'Anonim')

    errors = []

    if request.method == "GET":
        return render_template('login.html', errors=errors, username=visibleUser)

    username = request.form.get("username")
    password = request.form.get("password")

    if not (username and password):
        errors.append('Пожалуйста, заполните все поля')
        return render_template('login.html', errors=errors)

    conn = dbConnect()
    cur = conn.cursor()

    cur.execute("SELECT id, username, password_hash FROM users WHERE username = %s;", (username,))
    result = cur.fetchone()

    if result is None or not check_password_hash(result[2], password):
        errors.append("Неправильный логин или пароль")
        dbClose(cur, conn)
        return render_template('login.html', errors=errors)

    user_id, username, _ = result

    session['id'] = user_id
    session['username'] = username

    dbClose(cur, conn)
    return redirect("/index/")


@rgz.route('/index/logout')
def logout():
    session.clear()
    return redirect('/index/')


@rgz.route('/index/products/page/<int:page>', methods=['GET', 'POST'])
def products_page(page):
    user_id = session.get('id')
    username = session.get('username')

    if user_id is not None:
        # Получаем параметры offset и limit из запроса
        limit = 50
        offset = (page - 1) * limit

        conn = dbConnect()
        cur = conn.cursor()

        if request.method == 'POST':
            action = request.form.get('action')
            product_id = request.form.get('product_id')

            if action == 'add':
                cur.execute("INSERT INTO products (id, article_number, name, quantity) VALUES (%s, %s, %s, 1) ON CONFLICT (id) DO UPDATE SET quantity = products.quantity + 1 RETURNING id;",
                            (product_id, '', '',))
            elif action == 'remove':
                cur.execute("UPDATE products SET quantity = GREATEST(quantity - 1, 0) WHERE id = %s RETURNING id;",
                            (product_id,))
                cur.execute("DELETE FROM products WHERE id = %s AND quantity = 0;",
                            (product_id,))
            elif action == 'add_custom':
                # Добавление нового товара с введенными параметрами
                article_number = request.form.get('article_number')
                name = request.form.get('name')
                quantity = request.form.get('quantity')

                cur.execute("INSERT INTO products (article_number, name, quantity) VALUES (%s, %s, %s);",
                            (article_number, name, quantity))

            conn.commit()

        # Выполняем запрос к базе данных для получения товаров на странице
        cur.execute("SELECT * FROM products ORDER BY id LIMIT %s OFFSET %s;", (limit, offset))
        products = cur.fetchall()

        # Выполняем запрос к базе данных для получения общего количества товаров
        cur.execute("SELECT COUNT(*) FROM products;")
        total_count = cur.fetchone()[0]

        dbClose(cur, conn)

        # Рассчитываем количество страниц для пагинации
        total_pages = math.ceil(total_count / limit)

        # Проверяем, что запрошенная страница существует
        if 1 <= page <= total_pages:
            return render_template('products_page.html', products=products, username=username, offset=offset, limit=limit,
                                   total_count=total_count, total_pages=total_pages, current_page=page)
        else:
            return render_template('404.html'), 404
    else:
        return redirect('/index/login')
    

@rgz.route('/index/order', methods=['POST', 'GET'])
def order():
    user_id = session.get('id')
    username = session.get('username')

    if user_id is not None:
        conn = dbConnect()
        cur = conn.cursor()

        # Получаем все товары из базы данных
        cur.execute("SELECT * FROM products;")
        products = cur.fetchall()

        if request.method == 'POST':
            # Обработка формы заказа
            order_name = request.form.get('order_name')
            print(f"Order Name: {order_name}")

            # Проверяем, есть ли выбранные товары в наличии
            order_valid = True
            unavailable_products = []

            # Создаем запись в таблице orders
            cur.execute("INSERT INTO orders (user_id, order_name) VALUES (%s, %s) RETURNING id;", (user_id, order_name))
            order_id = cur.fetchone()[0]
            print(f"Order ID: {order_id}")

            # Добавляем товары в таблицу order_items
            for product_id in request.form.getlist('selected_products[]'):
                quantity = request.form.get(f'quantity_{product_id}')

                if quantity is not None and quantity.isdigit():
                    # Проверяем, что product_id не пустой и является числом
                    if product_id and product_id.isdigit():
                        product_id = int(product_id)

                        # Проверяем существование товара и наличие достаточного количества
                        cur.execute("SELECT id, quantity FROM products WHERE id = %s;", (product_id,))
                        result = cur.fetchone()

                        if result:
                            available_quantity = result[1]

                            if available_quantity >= int(quantity) > 0:
                                # Вставляем данные в order_items
                                cur.execute("INSERT INTO order_items (order_id, product_id, quantity) VALUES (%s, %s, %s);",
                                            (order_id, product_id, quantity))
                            else:
                                order_valid = False
                                unavailable_products.append(product_id)
                        else:
                            order_valid = False
                            unavailable_products.append(product_id)
                    else:
                        order_valid = False
                        unavailable_products.append(product_id)
                else:
                    order_valid = False
                    unavailable_products.append(product_id)

            if order_valid:
                conn.commit()
                flash('Заказ успешно оформлен!', 'success')
                return redirect('/index/order')
            else:
                # Если заказ не валиден, отменяем создание заказа
                cur.execute("DELETE FROM orders WHERE id = %s;", (order_id,))
                conn.commit()
                flash(f"Товары с ID {', '.join(map(str, unavailable_products))} не найдены или их количество недостаточно. Заказ отменен.", 'error')

        dbClose(cur, conn)

        return render_template('order_page.html', products=products, username=username)
    else:
        return redirect('/index/login')


@rgz.route('/index/orders', methods=['GET'])
def orders_page():
    user_id = session.get('id')
    username = session.get('username')

    if user_id is not None:
        conn = dbConnect()
        cur = conn.cursor()

        # Получаем все заказы пользователя из базы данных
        cur.execute("SELECT id, order_name, order_time FROM orders WHERE user_id = %s;", (user_id,))
        orders = cur.fetchall()

        dbClose(cur, conn)

        return render_template('orders_page.html', orders=orders, username=username)
    else:
        return redirect('/index/login')


@rgz.route('/index/order/details/<int:order_id>', methods=['GET'])
def order_details_page(order_id):
    user_id = session.get('id')
    username = session.get('username')

    if user_id is not None:
        conn = dbConnect()
        cur = conn.cursor()

        # Получаем детали заказа из базы данных, включая статус
        cur.execute("""
            SELECT oi.quantity, p.id, p.name, o.paid
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            JOIN orders o ON oi.order_id = o.id
            WHERE oi.order_id = %s;
        """, (order_id,))
        order_details = cur.fetchall()

        # Получаем информацию о самом заказе
        cur.execute("SELECT order_name, order_time, paid FROM orders WHERE id = %s AND user_id = %s;", (order_id, user_id))
        order_info = cur.fetchone()

        dbClose(cur, conn)

        return render_template('order_details_page.html', order_id=order_id, order_info=order_info, order_details=order_details, username=username)
    else:
        return redirect('/index/login')


@rgz.route('/index/order/pay/<int:order_id>', methods=['POST'])
def pay_order(order_id):
    user_id = session.get('id')

    if user_id is not None:
        conn = dbConnect()
        cur = conn.cursor()

        # Проверяем, что пользователь является владельцем заказа
        cur.execute("SELECT id FROM orders WHERE id = %s AND user_id = %s;", (order_id, user_id))
        result = cur.fetchone()

        if result:
            # Присваиваем статус оплачен
            cur.execute("UPDATE orders SET paid = TRUE WHERE id = %s;", (order_id,))

            # Уменьшаем количество товаров в таблице products
            for detail in request.form.getlist('order_details[]'):
                product_id, quantity = map(int, detail.split('_'))
                cur.execute("UPDATE products SET quantity = quantity - %s WHERE id = %s;", (quantity, product_id))

            conn.commit()
            flash('Статус оплачен успешно присвоен!', 'success')
        else:
            flash('Доступ запрещен!', 'error')

        dbClose(cur, conn)
        return redirect(f'/index/order/details/{order_id}')
    else:
        return redirect('/index/login')


# Добавьте новый роут для отмены оплаты заказа
@rgz.route('/index/order/cancel_payment/<int:order_id>', methods=['POST'])
def cancel_payment(order_id):
    user_id = session.get('id')

    if user_id is not None:
        conn = dbConnect()
        cur = conn.cursor()

        # Проверяем, что пользователь является владельцем заказа
        cur.execute("SELECT id, paid FROM orders WHERE id = %s AND user_id = %s;", (order_id, user_id))
        result = cur.fetchone()

        if result:
            order_id, paid = result

            if paid:
                # Отменяем оплату, устанавливаем статус "не оплачен"
                cur.execute("UPDATE orders SET paid = FALSE WHERE id = %s;", (order_id,))

                # Возвращаем количество товаров в исходное состояние
                for detail in request.form.getlist('order_details[]'):
                    product_id, quantity = map(int, detail.split('_'))
                    cur.execute("UPDATE products SET quantity = quantity + %s WHERE id = %s;", (quantity, product_id))

                conn.commit()
                flash('Оплата успешно отменена!', 'success')
            else:
                flash('Заказ не был оплачен!', 'error')
        else:
            flash('Доступ запрещен!', 'error')

        dbClose(cur, conn)
        return redirect(f'/index/order/details/{order_id}')
    else:
        return redirect('/index/login')


# Добавляем новый роут для удаления заказа
@rgz.route('/index/order/delete/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    user_id = session.get('id')

    if user_id is not None:
        conn = dbConnect()
        cur = conn.cursor()

        # Проверяем, что пользователь является владельцем заказа
        cur.execute("SELECT id, paid FROM orders WHERE id = %s AND user_id = %s;", (order_id, user_id))
        result = cur.fetchone()

        if result:
            order_id, paid = result

            # Если заказ оплачен, отменяем оплату
            if paid:
                # Отменяем оплату, устанавливаем статус "не оплачен"
                cur.execute("UPDATE orders SET paid = FALSE WHERE id = %s;", (order_id,))

                # Возвращаем количество товаров в исходное состояние
                for detail in request.form.getlist('order_details[]'):
                    product_id, quantity = map(int, detail.split('_'))
                    cur.execute("UPDATE products SET quantity = quantity + %s WHERE id = %s;", (quantity, product_id))

                conn.commit()
                flash('Оплата успешно отменена!', 'success')

            # Удаляем связанные данные из таблицы order_items
            cur.execute("DELETE FROM order_items WHERE order_id = %s;", (order_id,))

            # Удаляем заказ из таблицы orders
            cur.execute("DELETE FROM orders WHERE id = %s;", (order_id,))
            conn.commit()
            flash('Заказ успешно удален!', 'success')

        else:
            flash('Доступ запрещен!', 'error')

        dbClose(cur, conn)
        return redirect('/index/orders')
    else:
        return redirect('/index/login')
