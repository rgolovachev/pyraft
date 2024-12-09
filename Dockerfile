FROM python:3.11

WORKDIR /app

COPY raft.py /app/
COPY raft_pb2_grpc.py /app/
COPY raft_pb2.py /app/
COPY config.conf /app/
COPY requirements.txt /app/

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 7001
EXPOSE 7002
EXPOSE 7003
ENTRYPOINT [ "sh", "-c", "python3 raft.py $NODE_ID" ]
