from django_q.scheduler import Scheduler
# from .tasks import generate_invoices

scheduler = Scheduler()
scheduler.add_task('generate_invoices',delay=30000)

scheduler.run()

