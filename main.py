import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum

class OrderStatus(Enum):
    PENDING = "ожидает"
    ASSIGNED = "назначен"
    PICKED_UP = "забран"
    DELIVERING = "доставляется"
    COMPLETED = "доставлен"
    CANCELLED = "отменён"

class DeliveryType(Enum):
    EXPRESS = "экспресс"
    STANDARD = "обычная"

class Order:
    def __init__(self, order_id: str, customer_name: str, address: str,
                 phone: str, delivery_type: DeliveryType):
        self.order_id = order_id
        self.customer_name = customer_name
        self.address = address
        self.phone = phone
        self.delivery_type = delivery_type
        self.status = OrderStatus.PENDING
        self.courier_id: Optional[str] = None
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

class Courier:
    def __init__(self, courier_id: str, name: str, phone: str, max_orders: int = 3):
        self.courier_id = courier_id
        self.name = name
        self.phone = phone
        self.max_orders = max_orders
        self.current_orders: List[str] = []
        self.is_available = True

class IOrderRepository:
    def save(self, order: Order) -> None: pass
    def find_by_id(self, order_id: str) -> Optional[Order]: pass
    def find_all(self) -> List[Order]: pass
    def update(self, order: Order) -> None: pass

class ICourierRepository:
    def save(self, courier: Courier) -> None: pass
    def find_by_id(self, courier_id: str) -> Optional[Courier]: pass
    def find_all_available(self) -> List[Courier]: pass
    def update(self, courier: Courier) -> None: pass

class INotificationService:
    async def notify_courier(self, courier: Courier, order: Order) -> None: pass
    async def notify_customer(self, order: Order, message: str) -> None: pass

class IDeliveryService:
    async def assign_order(self, order_id: str) -> bool: pass
    async def update_status(self, order_id: str, status: OrderStatus,
                            courier_id: Optional[str] = None) -> bool: pass
    async def get_order_info(self, order_id: str) -> Optional[Order]: pass

class OrderRepository(IOrderRepository):
    def __init__(self):
        self._orders: Dict[str, Order] = {}

    def save(self, order: Order) -> None:
        self._orders[order.order_id] = order

    def find_by_id(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def find_all(self) -> List[Order]:
        return list(self._orders.values())

    def update(self, order: Order) -> None:
        order.updated_at = datetime.now()
        self._orders[order.order_id] = order

class CourierRepository(ICourierRepository):
    def __init__(self):
        self._couriers: Dict[str, Courier] = {}

    def save(self, courier: Courier) -> None:
        self._couriers[courier.courier_id] = courier

    def find_by_id(self, courier_id: str) -> Optional[Courier]:
        return self._couriers.get(courier_id)

    def find_all_available(self) -> List[Courier]:
        return [c for c in self._couriers.values()
                if c.is_available and len(c.current_orders) < c.max_orders]

    def update(self, courier: Courier) -> None:
        self._couriers[courier.courier_id] = courier

class NotificationService(INotificationService):
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    async def notify_courier(self, courier: Courier, order: Order) -> None:
        self.logger.info(f"Уведомление курьера {courier.name}: новый заказ {order.order_id} на {order.address}")

    async def notify_customer(self, order: Order, message: str) -> None:
        self.logger.info(f"Уведомление клиента {order.customer_name}: {message}")

class DeliveryService(IDeliveryService):
    def __init__(self, order_repo: IOrderRepository,
                 courier_repo: ICourierRepository,
                 notification_service: INotificationService,
                 logger: logging.Logger):
        self.order_repo = order_repo
        self.courier_repo = courier_repo
        self.notification = notification_service
        self.logger = logger

    async def assign_order(self, order_id: str) -> bool:
        order = self.order_repo.find_by_id(order_id)
        if not order or order.status != OrderStatus.PENDING:
            self.logger.warning(f"Заказ {order_id} не может быть назначен")
            return False

        available_couriers = self.courier_repo.find_all_available()
        if not available_couriers:
            self.logger.warning(f"Нет доступных курьеров для заказа {order_id}")
            return False

        courier = available_couriers[0]
        order.courier_id = courier.courier_id
        order.status = OrderStatus.ASSIGNED
        courier.current_orders.append(order.order_id)
        if len(courier.current_orders) >= courier.max_orders:
            courier.is_available = False

        self.order_repo.update(order)
        self.courier_repo.update(courier)
        await self.notification.notify_courier(courier, order)
        await self.notification.notify_customer(order, f"Курьер {courier.name} назначен")
        self.logger.info(f"Заказ {order_id} назначен курьеру {courier.name}")
        return True

    async def update_status(self, order_id: str, status: OrderStatus,
                           courier_id: Optional[str] = None) -> bool:
        order = self.order_repo.find_by_id(order_id)
        if not order:
            self.logger.error(f"Заказ {order_id} не найден")
            return False

        if courier_id and order.courier_id != courier_id:
            self.logger.warning(f"Курьер {courier_id} не назначен на заказ {order_id}")
            return False

        old_status = order.status
        order.status = status
        self.order_repo.update(order)

        if status == OrderStatus.COMPLETED and order.courier_id:
            courier = self.courier_repo.find_by_id(order.courier_id)
            if courier:
                if order.order_id in courier.current_orders:
                    courier.current_orders.remove(order.order_id)
                if len(courier.current_orders) < courier.max_orders:
                    courier.is_available = True
                self.courier_repo.update(courier)

        await self.notification.notify_customer(order, f"Статус заказа: {status.value}")
        self.logger.info(f"Заказ {order_id}: {old_status.value} -> {status.value}")
        return True

    async def get_order_info(self, order_id: str) -> Optional[Order]:
        return self.order_repo.find_by_id(order_id)

class TelegramBot:
    def __init__(self, token: str, delivery_service: IDeliveryService,
                 order_repo: IOrderRepository, courier_repo: ICourierRepository,
                 logger: logging.Logger):
        self.token = token
        self.delivery_service = delivery_service
        self.order_repo = order_repo
        self.courier_repo = courier_repo
        self.logger = logger
        self.last_created_order_id = None

    async def send_message(self, chat_id: str, text: str) -> None:
        self.logger.info(f"Отправка сообщения в {chat_id}: {text}")

    async def handle_order_command(self, chat_id: str, args: List[str]) -> None:
        if len(args) < 4:
            await self.send_message(chat_id, "Формат: /order <ФИО> <адрес> <телефон> [express|standard]")
            return

        delivery_type = DeliveryType.STANDARD
        if len(args) > 4 and args[4].lower() == "express":
            delivery_type = DeliveryType.EXPRESS

        order_id = f"ORD_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.last_created_order_id = order_id

        order = Order(order_id, args[0], args[1], args[2], delivery_type)
        self.order_repo.save(order)

        await self.send_message(chat_id, f"Заказ #{order_id} создан. Статус: {order.status.value}")
        await self.delivery_service.assign_order(order_id)
        return order_id

    async def handle_status_command(self, chat_id: str, args: List[str]) -> None:
        if not args:
            await self.send_message(chat_id, "Формат: /status <номер заказа>")
            return

        order = await self.delivery_service.get_order_info(args[0])
        if not order:
            await self.send_message(chat_id, f"Заказ {args[0]} не найден")
            return

        response = f"Заказ #{order.order_id}\nКлиент: {order.customer_name}\n"
        response += f"Адрес: {order.address}\nСтатус: {order.status.value}\n"
        response += f"Тип: {order.delivery_type.value}"
        if order.courier_id:
            response += f"\nКурьер: {order.courier_id}"
        await self.send_message(chat_id, response)

    async def handle_courier_command(self, chat_id: str, args: List[str]) -> None:
        if len(args) < 3:
            await self.send_message(chat_id, "Формат: /courier <ID> <ФИО> <телефон>")
            return

        courier = Courier(args[0], args[1], args[2])
        self.courier_repo.save(courier)
        await self.send_message(chat_id, f"Курьер {courier.name} зарегистрирован")

    async def handle_deliver_command(self, chat_id: str, args: List[str]) -> None:
        if len(args) < 2:
            await self.send_message(chat_id, "Формат: /deliver <заказ> [pickup|delivering|complete]")
            return

        order_id = args[0]
        action = args[1] if len(args) > 1 else ""

        status_map = {
            "pickup": OrderStatus.PICKED_UP,
            "delivering": OrderStatus.DELIVERING,
            "complete": OrderStatus.COMPLETED
        }

        if action not in status_map:
            await self.send_message(chat_id, "Действия: pickup, delivering, complete")
            return

        result = await self.delivery_service.update_status(order_id, status_map[action])
        if result:
            await self.send_message(chat_id, f"Статус заказа {order_id} обновлён -> {status_map[action].value}")
        else:
            await self.send_message(chat_id, f"Ошибка обновления статуса заказа {order_id}")

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("DeliveryService")

    order_repo = OrderRepository()
    courier_repo = CourierRepository()
    notification = NotificationService(logger)
    delivery_service = DeliveryService(order_repo, courier_repo, notification, logger)

    test_courier = Courier("C001", "Иван Петров", "+79991234567", 5)
    courier_repo.save(test_courier)
    logger.info("Тестовый курьер добавлен: C001 - Иван Петров")

    bot = TelegramBot("test_token", delivery_service, order_repo, courier_repo, logger)

    created_order_id = await bot.handle_order_command("chat_1", ["Анна Смирнова", "ул. Ленина 10", "+79991112233", "express"])

    if created_order_id:
        await asyncio.sleep(1)
        await bot.handle_status_command("chat_1", [created_order_id])

        await asyncio.sleep(1)
        await bot.handle_deliver_command("chat_1", [created_order_id, "pickup"])

        await asyncio.sleep(1)
        await bot.handle_deliver_command("chat_1", [created_order_id, "delivering"])

        await asyncio.sleep(1)
        await bot.handle_deliver_command("chat_1", [created_order_id, "complete"])

        await asyncio.sleep(1)
        await bot.handle_status_command("chat_1", [created_order_id])

    all_orders = order_repo.find_all()
    logger.info(f"Всего заказов в системе: {len(all_orders)}")
    for order in all_orders:
        logger.info(f"  - {order.order_id}: {order.status.value} (клиент: {order.customer_name})")

if __name__ == "__main__":
    asyncio.run(main())