# slim It works well with lxml which needs C compilation.
FROM python:3.12-slim

# set the working directory in the container
WORKDIR /app 

# deliberately copy only requirements, each layer is cached and doing this prevents the next RUN pip install on rebuild saving time
COPY requirements.txt .
#  --no cache thingy to avoid storing pip's cache oiin the image
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000

# security best practice so that if the app is compromised there is no root access
RUN useradd --create-home appuser
# switches to appuser for all subsequent commands (including CMD)
USER appuser

# uses 0.0.0.0 instead of 127.0.0.1 so the app is accessible outside the container  
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]