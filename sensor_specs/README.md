## Where to put files?
- *.yaml -> /etc/mini-air-quality/sensor-spec/
- set_envs.py -> don't put on the image, only to generate config
- sensors_config.ini -> /etc/mini-air-quality/
- envs.lock -> /etc/mini-air-quality/

## Other actions required
sensors_config.ini and envs.lock must have 766 access mask.
