FROM python:2.7
MAINTAINER Emre Demirors

RUN apt-get update && apt-get upgrade -y
ADD requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
RUN mkdir -p /opt/modsim/
ADD modsim/mbmap.py /opt/modsim/
ADD modsim/mbmap_test_device.xml /opt/modsim/
ADD modsim/modsim.py /opt/modsim/
EXPOSE 502


