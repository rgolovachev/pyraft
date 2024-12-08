FROM python:3.11

WORKDIR /app

COPY raft.py /app/
COPY raft_pb2_grpc.py /app/
COPY raft_pb2.py /app/
COPY config.conf /app/
COPY requirements.txt /app/

# RUN pip3 install grpcio
# RUN pip3 install grpcio-tools
# RUN pip3 install grpcio-reflection
RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["python3", "raft.py", "0"]
