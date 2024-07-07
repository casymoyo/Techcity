import redis

# Extract details from your URL
url = 'redis://default:FrvkpRENzvubHiJrDiRoQmVmdBjaNwFC@roundhouse.proxy.rlwy.net:24949'
password = 'FrvkpRENzvubHiJrDiRoQmVmdBjaNwFC'
host = 'roundhouse.proxy.rlwy.net'
port = 24949

# Create Redis connection
r = redis.Redis(host=host, port=port, password=password, db=0)

# Test connection
print(r.ping())  # Should print True if the connection is successful

from techcity.celery import app # Adjust import as per your project structure
result = app.send_task('techcity.tasks.add', args=[10, 20])
print(result.get())  # Should print 30
