#!/bin/sh

while [ 1 ]; do
	./qdot.py 3.dot &
	inotifywait -e modify qdot.py
	ps -ef|grep qdot.py | grep python|awk '{printf("%d", $2);}'|xargs kill
done

