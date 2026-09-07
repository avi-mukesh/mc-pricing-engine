FROM python:3.12-slim

# sets the working directory inside the container to /app
WORKDIR /app

# copy file from computer into the Docker image /app
COPY requirements.txt .

# run while the docker image is being built
# --no-cache-dir tells pip not to keep its downloaded package cache - helps keep the image smaller
RUN pip install --no-cache-dir -r requirements.txt

# copy the application code into /app
COPY pricing.py main.py ./

# what happens when you START a container from this image
CMD ["python3", "main.py"] 