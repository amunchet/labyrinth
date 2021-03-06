[![Labyrinth Tests](https://github.com/amunchet/labyrinth/actions/workflows/push.yml/badge.svg)](https://github.com/amunchet/labyrinth/actions/workflows/push.yml)

<img src="frontend/labyrinth/public/logo.png" height="100" alt="Labyrinth Logo" />

# Labyrinth
The beautiful network analyzer, mapper, and monitor.

<img src="frontend/labyrinth/public/img/screenshot.png"  alt="Labyrinth Screenshot" />

## Build
1.  Labyrinth is using **CVE-Search-Docker** (https://github.com/cve-search/CVE-Search-Docker) to provide vulnerability searching.  This exists as a submodule.  To correctly pull or initialize, you'll need two additional commands `git submodule init && git submodule init`.  Warning: It's a rather large folder.

## Install
1. `sudo bash install.sh` - this will walk you through the setup needed for Auth0 information.
2.  If you are running docker as non-root, then remove the top section from `install.sh` and re-run.

## FAQ
### 1.  Aren't you reinventing the wheel?
Sure - to some extent.  Labyrinth is built upon very solid projects: NMap, Ansible, and Telegraf.  

However, Labyrinth does some things better than other popular projects: 
- Labyrinth looks good.  Yes, you can use Grafana to make pretty good dashboards, but I want something that's naturally nice looking and simple.  Grafana dashboards are endlessly customizable, and by that virtue - never completed.  Grafana also struggles a little with multi-host displays - I wasn't able to make it look *quite* like I wanted.

- Labyrinth has better autodiscovery: port scanning.  Projects like Prometheus have auto discovery, but they are very cloud-centric.  Labyrinth fits best in a on-prem or hybrid situation, with many different kinds of clients joining and leaving.  TCP/UDP are some of the fundamental protocols: if you can't communicate over them, something's probably wrong.  Furthermore, Labyrinth wants to know if something unexpected has happened: a port being openend or closed, a new client that wasn't supposed to be in that subnet, etc.

- Labyrinth has simple management.  By using Ansible and Telegraf, it's very easy to provision from the web interface.  Don't want to do that?  No problem - the ports based nature of Labyrinth can give a good idea of network status without an agent.

- Labyrinth is easy.  Start it up as a docker, use the web interface, done - up and running in minutes.  If you want to get into Telegraf configuration files, you're able to do that.

### 2.  What does Labyrinth NOT do well?
Labyrinth is meant for hybrid, dynamic, check based network management.  For homogenous services or full cloud offerings, there are tons of better projects: Prometheus, ELK stack, Sensu Go, etc.  

Labyrinth also isn't built with metric analysis or time-series in mind - you can do them, but there are tons of better tools out there: Graylog, ELK, etc.

Labyrinth is built for smaller to midsize networks - I simply don't know how it works on large networks, since I'm building to solve my problem.

### 3.  Who is Labyrinth made for?
Labyrinth is for whatever poor sysadmin has a small to midsize network they can't keep up with - and they just want something easy and pretty to occasionally look at.  Whether that's a homelab admin or a one-man devops band, Labyrinth is here to help.

### 4.  Can you use it with Kubernetes?
You probably can use Labyrinth for K8, but there are plenty of better, specialized tools that you should probably use instead.

## Development
Start a development docker-compose stack with the following commands:
- `docker-compose -f docker-compose-development.yml up --build -d`
- Port `8100` will be the Vue frontend server.  Go there to start up the development server.
- Once the Vue frontend server has been started, navigate to `:8101` to see the live frontend.
- Certificates: you may need to point your browser to `:7200` to accept the self-signed certificate.  If you navigate to the frontend without doing that, you will receive "Network Error" messages.

# TODO
- Documentation on setting up Auth0 for the system.  Also notes on how to disable using auth (can just have it as an ENV variable in the docker compose)

# Other Wonderful Projects
- https://github.com/SabyasachiRana/WebMap - although this project is pretty quiet currently, this had lots of good ideas.  I just wish it was more of a network management tool than just scanning.
- Prometheus
- Sensu Go
- etc.
