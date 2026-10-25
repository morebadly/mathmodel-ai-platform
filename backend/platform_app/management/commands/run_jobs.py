import time
import threading
from django.core.management.base import BaseCommand
from platform_app.tasks import maintenance,media_tick,execution_tick
class Command(BaseCommand):
    help='Windows 本机联调任务循环；生产环境使用 Linux Celery worker 和 beat。'
    def add_arguments(self,parser):parser.add_argument('--once',action='store_true');parser.add_argument('--interval',type=int,default=5)
    def handle(self,*args,**options):
        stop=threading.Event()
        def worker(task):
            while not stop.is_set():
                try:task.run()
                except Exception as error:self.stderr.write('任务循环暂未完成：'+type(error).__name__)
                stop.wait(max(2,options['interval']))
        if options['once']:
            maintenance.run();media_tick.run();execution_tick.run();return
        for task in [media_tick,execution_tick]:threading.Thread(target=worker,args=(task,),daemon=True).start()
        while True:
            try:maintenance.run()
            except KeyboardInterrupt:stop.set();return
            except Exception as error:self.stderr.write('任务循环暂未完成：'+type(error).__name__)
            if options['once']:return
            time.sleep(max(2,options['interval']))
