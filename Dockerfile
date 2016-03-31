FROM python:2.7
MAINTAINER Emre Demirors

RUN apt-get update && apt-get upgrade -y
RUN pip install modbus_tk

