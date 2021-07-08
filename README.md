# Labyrinth
The beautiful network analyzer and mapper.

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