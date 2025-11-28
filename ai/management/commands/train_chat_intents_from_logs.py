from django.core.management.base import BaseCommand

from ai.models import ChatMessage


class Command(BaseCommand):
    help = "Проходится по логам чата и подготавливает данные для обучения NLP/intent моделей."

    def handle(self, *args, **options):
        total = ChatMessage.objects.count()
        assistant_messages = ChatMessage.objects.filter(role=ChatMessage.Role.ASSISTANT).count()
        user_messages = total - assistant_messages
        self.stdout.write(self.style.SUCCESS("Всего сообщений: %s" % total))
        self.stdout.write(f"Ответов ассистента: {assistant_messages}")
        self.stdout.write(f"Сообщений пользователей: {user_messages}")
        # TODO: выгружать диалоги и обучать намерения
        self.stdout.write("Подготовка к обучению завершена (заглушка).")
