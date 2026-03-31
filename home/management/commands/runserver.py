"""
Кастомная команда runserver, которая запускает и Django сервер, и Django-Q воркер одновременно
"""
import subprocess
import sys
import os
import time
from django.core.management.commands.runserver import Command as RunserverCommand


class Command(RunserverCommand):
    help = 'Запускает Django сервер и Django-Q воркер одновременно'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--no-qcluster',
            action='store_true',
            help='Запустить только Django сервер без Django-Q',
        )

    def handle(self, *args, **options):
        """
        Переопределяем handle для запуска Django-Q в отдельном процессе
        """
        # Проверяем, нужно ли запускать qcluster
        run_qcluster = not options.get('no_qcluster', False)
        
        qcluster_process = None
        
        if run_qcluster:
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(self.style.SUCCESS('🚀 LukInterLab - Запуск проекта'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('🔄 Запуск Django-Q воркера...'))
            
            try:
                # Запускаем qcluster как subprocess
                qcluster_process = subprocess.Popen(
                    [sys.executable, 'manage.py', 'qcluster'],
                    cwd=os.getcwd(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Даем время на запуск
                time.sleep(1)
                
                # Проверяем, что процесс запущен
                if qcluster_process.poll() is None:
                    self.stdout.write(self.style.SUCCESS('✅ Django-Q воркер успешно запущен'))
                else:
                    self.stdout.write(self.style.WARNING('⚠️  Django-Q не запущен, проверьте настройки'))
                
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'⚠️  Не удалось запустить Django-Q: {e}'))
            
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('🌐 Запуск Django сервера...'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write('')
        
        try:
            # Запускаем стандартный runserver
            super().handle(*args, **options)
        except KeyboardInterrupt:
            # При Ctrl+C останавливаем и Django-Q
            if qcluster_process and qcluster_process.poll() is None:
                self.stdout.write('')
                self.stdout.write(self.style.WARNING('⏹️  Остановка Django-Q воркера...'))
                qcluster_process.terminate()
                qcluster_process.wait(timeout=5)
                self.stdout.write(self.style.SUCCESS('✅ Django-Q остановлен'))
            raise

