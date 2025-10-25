web: gunicorn --bind :8000 --workers 2 --threads 4 --timeout 300 --keep-alive 2 --max-requests 1000 --max-requests-jitter 100 application:application
