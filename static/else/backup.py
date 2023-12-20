@rgz.route('/index/order', methods=['GET', 'POST'])
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


            # Создаем запись в таблице orders
            cur.execute("INSERT INTO orders (user_id, order_name) VALUES (%s, %s) RETURNING id;", (user_id, order_name))
            order_id = cur.fetchone()[0]
            print(f"Order ID: {order_id}")


            # Добавляем товары в таблицу order_items
            for product_id in request.form.getlist('selected_products[]'):
                quantity = request.form.get(f'quantity_{product_id}')
                print(f"Received product_id: {product_id}, quantity: {quantity}")

                if quantity is not None and quantity.isdigit():
                    # Проверяем, что product_id не пустой и является числом
                    if product_id and product_id.isdigit():
                        product_id = int(product_id)
                        
                        # Проверяем существование товара перед вставкой
                        cur.execute("SELECT id FROM products WHERE id = %s;", (product_id,))
                        result = cur.fetchone()

                        if result:
                            # Вставляем данные в order_items
                            cur.execute("INSERT INTO order_items (order_id, product_id, quantity) VALUES (%s, %s, %s);",
                                        (order_id, product_id, quantity))
                        else:
                            flash(f"Товар с id {product_id} не найден.", 'error')
                    else:
                        flash("Неверное значение product_id.", 'error')
                else:
                    flash("Неверное значение quantity.", 'error')

            conn.commit()

            flash('Заказ успешно оформлен!', 'success')
            return redirect('/index/order')

        dbClose(cur, conn)

        return render_template('order_page.html', products=products, username=username)
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

            for product_id in request.form.getlist('selected_products[]'):
                quantity = request.form.get(f'quantity_{product_id}')
                print(f"Received product_id: {product_id}, quantity: {quantity}")

                if quantity is not None and quantity.isdigit():
                    # Проверяем, что product_id не пустой и является числом
                    if product_id and product_id.isdigit():
                        product_id = int(product_id)

                        # Проверяем существование товара перед вставкой
                        cur.execute("SELECT id, quantity FROM products WHERE id = %s;", (product_id,))
                        result = cur.fetchone()

                        if result:
                            available_quantity = result[1]

                            # Проверяем, что количество товара достаточно
                            if available_quantity < int(quantity):
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
                # Создаем запись в таблице orders
                cur.execute("INSERT INTO orders (user_id, order_name) VALUES (%s, %s) RETURNING id;", (user_id, order_name))
                order_id = cur.fetchone()[0]
                print(f"Order ID: {order_id}")

                # Добавляем товары в таблицу order_items и обновляем количество товаров в таблице products
                for product_id in request.form.getlist('selected_products[]'):
                    quantity = request.form.get(f'quantity_{product_id}')
                    print(f"Received product_id: {product_id}, quantity: {quantity}")

                    if quantity is not None and quantity.isdigit():
                        # Проверяем, что product_id не пустой и является числом
                        if product_id and product_id.isdigit():
                            product_id = int(product_id)

                            # Вставляем данные в order_items
                            cur.execute("INSERT INTO order_items (order_id, product_id, quantity) VALUES (%s, %s, %s);",
                                        (order_id, product_id, quantity))

                            # Обновляем количество товаров в таблице products
                            cur.execute("UPDATE products SET quantity = quantity - %s WHERE id = %s;", (quantity, product_id))
                        else:
                            flash("Неверное значение product_id.", 'error')
                    else:
                        flash("Неверное значение quantity.", 'error')

                conn.commit()
                flash('Заказ успешно оформлен!', 'success')
                return redirect('/index/order')
            else:
                flash(f"Товары с ID {', '.join(map(str, unavailable_products))} не найдены или их количество недостаточно.", 'error')

        dbClose(cur, conn)

        return render_template('order_page.html', products=products, username=username)
    else:
        return redirect('/index/login')