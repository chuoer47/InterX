.PHONY: start-stable start-multi stop status probe monitor monitor-stop score cache-test smoke stream

start-stable:
	bash ops/interx-gateway start stable

start-multi:
	bash ops/interx-gateway start multi

stop:
	bash ops/interx-gateway stop

status:
	bash ops/interx-gateway status

probe:
	. .venv/bin/activate && python scripts/routing_probe.py

monitor:
	bash ops/interx-gateway monitor

monitor-stop:
	bash ops/interx-gateway monitor-stop

score:
	. .venv/bin/activate && python scripts/score_upstreams.py

cache-test:
	. .venv/bin/activate && python scripts/cache_test.py

smoke:
	. .venv/bin/activate && python scripts/smoke_test.py

stream:
	. .venv/bin/activate && python scripts/stream_test.py
