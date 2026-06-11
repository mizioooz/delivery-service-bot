import pytest
from unittest.mock import Mock, AsyncMock

from main import (
    Order, Courier, OrderStatus, DeliveryType,
    OrderRepository, CourierRepository,
    DeliveryService, NotificationService
)

class TestOrderRepository:
    def test_save_and_find_order(self):
        repo = OrderRepository()
        order = Order("ORD_001", "Тест", "Адрес", "123", DeliveryType.STANDARD)
        repo.save(order)
        found = repo.find_by_id("ORD_001")
        assert found is not None
        assert found.order_id == "ORD_001"

    def test_find_nonexistent_order(self):
        repo = OrderRepository()
        found = repo.find_by_id("NONE")
        assert found is None

    def test_find_all_orders(self):
        repo = OrderRepository()
        repo.save(Order("ORD_001", "A", "Addr1", "111", DeliveryType.STANDARD))
        repo.save(Order("ORD_002", "B", "Addr2", "222", DeliveryType.EXPRESS))
        assert len(repo.find_all()) == 2

    def test_update_order(self):
        repo = OrderRepository()
        order = Order("ORD_001", "Тест", "Адрес", "123", DeliveryType.STANDARD)
        repo.save(order)
        order.status = OrderStatus.ASSIGNED
        repo.update(order)
        updated = repo.find_by_id("ORD_001")
        assert updated.status == OrderStatus.ASSIGNED

class TestCourierRepository:
    def test_save_and_find_courier(self):
        repo = CourierRepository()
        courier = Courier("C001", "Иван", "123", 3)
        repo.save(courier)
        found = repo.find_by_id("C001")
        assert found is not None
        assert found.name == "Иван"

    def test_find_available_couriers(self):
        repo = CourierRepository()
        c1 = Courier("C001", "Иван", "111", 2)
        c2 = Courier("C002", "Петр", "222", 2)
        c2.is_available = False
        repo.save(c1)
        repo.save(c2)
        available = repo.find_all_available()
        assert len(available) == 1
        assert available[0].courier_id == "C001"

class TestDeliveryService:
    @pytest.mark.asyncio
    async def test_assign_order_success(self):
        order_repo = OrderRepository()
        courier_repo = CourierRepository()

        mock_notification = Mock()
        mock_notification.notify_courier = AsyncMock()
        mock_notification.notify_customer = AsyncMock()

        mock_logger = Mock()

        service = DeliveryService(order_repo, courier_repo, mock_notification, mock_logger)

        order = Order("ORD_001", "Тест", "Адрес", "123", DeliveryType.STANDARD)
        courier = Courier("C001", "Иван", "111", 2)
        order_repo.save(order)
        courier_repo.save(courier)

        result = await service.assign_order("ORD_001")
        assert result is True

        updated_order = order_repo.find_by_id("ORD_001")
        assert updated_order.status == OrderStatus.ASSIGNED
        assert updated_order.courier_id == "C001"

    @pytest.mark.asyncio
    async def test_assign_order_no_courier(self):
        order_repo = OrderRepository()
        courier_repo = CourierRepository()

        mock_notification = Mock()
        mock_notification.notify_courier = AsyncMock()
        mock_notification.notify_customer = AsyncMock()

        mock_logger = Mock()

        service = DeliveryService(order_repo, courier_repo, mock_notification, mock_logger)

        order = Order("ORD_001", "Тест", "Адрес", "123", DeliveryType.STANDARD)
        order_repo.save(order)

        result = await service.assign_order("ORD_001")
        assert result is False

    @pytest.mark.asyncio
    async def test_update_status_to_completed(self):
        order_repo = OrderRepository()
        courier_repo = CourierRepository()

        mock_notification = Mock()
        mock_notification.notify_customer = AsyncMock()

        mock_logger = Mock()

        service = DeliveryService(order_repo, courier_repo, mock_notification, mock_logger)

        order = Order("ORD_001", "Тест", "Адрес", "123", DeliveryType.STANDARD)
        courier = Courier("C001", "Иван", "111", 2)
        order.courier_id = "C001"
        order.status = OrderStatus.DELIVERING
        courier.current_orders.append("ORD_001")
        courier.is_available = False

        order_repo.save(order)
        courier_repo.save(courier)

        result = await service.update_status("ORD_001", OrderStatus.COMPLETED)
        assert result is True

        updated_order = order_repo.find_by_id("ORD_001")
        assert updated_order.status == OrderStatus.COMPLETED

        updated_courier = courier_repo.find_by_id("C001")
        assert "ORD_001" not in updated_courier.current_orders

    @pytest.mark.asyncio
    async def test_update_status_order_not_found(self):
        order_repo = OrderRepository()
        courier_repo = CourierRepository()

        mock_notification = Mock()
        mock_notification.notify_customer = AsyncMock()

        mock_logger = Mock()

        service = DeliveryService(order_repo, courier_repo, mock_notification, mock_logger)

        result = await service.update_status("NONE", OrderStatus.COMPLETED)
        assert result is False

    @pytest.mark.asyncio
    async def test_update_status_wrong_courier(self):
        order_repo = OrderRepository()
        courier_repo = CourierRepository()

        mock_notification = Mock()
        mock_notification.notify_customer = AsyncMock()

        mock_logger = Mock()

        service = DeliveryService(order_repo, courier_repo, mock_notification, mock_logger)

        order = Order("ORD_001", "Тест", "Адрес", "123", DeliveryType.STANDARD)
        order.courier_id = "C001"
        order_repo.save(order)

        result = await service.update_status("ORD_001", OrderStatus.PICKED_UP, "C002")
        assert result is False

    @pytest.mark.asyncio
    async def test_update_status_pickup(self):
        order_repo = OrderRepository()
        courier_repo = CourierRepository()

        mock_notification = Mock()
        mock_notification.notify_customer = AsyncMock()

        mock_logger = Mock()

        service = DeliveryService(order_repo, courier_repo, mock_notification, mock_logger)

        order = Order("ORD_001", "Тест", "Адрес", "123", DeliveryType.STANDARD)
        order.courier_id = "C001"
        order.status = OrderStatus.ASSIGNED
        order_repo.save(order)

        result = await service.update_status("ORD_001", OrderStatus.PICKED_UP)
        assert result is True

        updated_order = order_repo.find_by_id("ORD_001")
        assert updated_order.status == OrderStatus.PICKED_UP

class TestOrder:
    def test_order_creation(self):
        order = Order("ORD_001", "Анна", "ул. Ленина 10", "123", DeliveryType.EXPRESS)
        assert order.order_id == "ORD_001"
        assert order.customer_name == "Анна"
        assert order.delivery_type == DeliveryType.EXPRESS
        assert order.status == OrderStatus.PENDING
        assert order.courier_id is None

class TestCourier:
    def test_courier_creation(self):
        courier = Courier("C001", "Иван Петров", "123", 5)
        assert courier.courier_id == "C001"
        assert courier.name == "Иван Петров"
        assert courier.max_orders == 5
        assert courier.current_orders == []
        assert courier.is_available is True

class TestNotificationService:
    @pytest.mark.asyncio
    async def test_notify_courier(self):
        import logging
        logger = logging.getLogger("test")
        notification = NotificationService(logger)

        courier = Courier("C001", "Иван", "123")
        order = Order("ORD_001", "Тест", "Адрес", "123", DeliveryType.STANDARD)

        await notification.notify_courier(courier, order)

    @pytest.mark.asyncio
    async def test_notify_customer(self):
        import logging
        logger = logging.getLogger("test")
        notification = NotificationService(logger)

        order = Order("ORD_001", "Тест", "Адрес", "123", DeliveryType.STANDARD)

        await notification.notify_customer(order, "Тестовое сообщение")

class TestTelegramBot:
    @pytest.mark.asyncio
    async def test_send_message(self):
        import logging
        logger = logging.getLogger("test")

        mock_delivery = Mock()
        mock_order_repo = Mock()
        mock_courier_repo = Mock()

        from main import TelegramBot
        bot = TelegramBot("test_token", mock_delivery, mock_order_repo, mock_courier_repo, logger)

        await bot.send_message("chat_123", "Тест")

    @pytest.mark.asyncio
    async def test_handle_order_command_invalid_args(self):
        import logging
        logger = logging.getLogger("test")

        mock_delivery = Mock()
        mock_order_repo = Mock()
        mock_courier_repo = Mock()

        from main import TelegramBot
        bot = TelegramBot("test_token", mock_delivery, mock_order_repo, mock_courier_repo, logger)

        await bot.handle_order_command("chat_123", ["arg1"])