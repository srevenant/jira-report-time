# jira time reporter

Reporting on worked time from Jira is challenging... if you want more than the basics.  The plugins available for cloud are even more difficult because they focus on a "timesheet" -- which frankly, can be a negative to productivity with software engineers.

I want a report that just shows time logged so we can know where time is going, without people feeling like they are "punching a clock" to flip burgers.

Furthermore, we need a report that groups time for billing, where the grouping can be a multi-select field with a list of clients (and you can then map a single issue to be billed to multiple clients).

This tool is meant to be run via a schedule (weekly), supports a grouping, maps worklog entries, runs within a container, and will send the report via slack.

# philosophy

Project management tools are often designed with the user experience focused on the project manager.  I believe this creates an environment where the larger user base (the devs for software engineering) are subject to processes that can be difficult, frustrating, and create friction in the process.

Getting an accurate log of time for tech work is hard.  So my philosophy is to make it as easy to log the time as possible (no required fields, no mandatory time log on transitions, etc), and even to make or use bots that will log it for you (see stratejos).

This focuses the UX of the project management tool onto the users, rather than the PM's, and I think although the time may not be curated as cleanly, it will definitely be more accurate.

# setup

You need docker..

It stores on slack (not great, but it was the best option we could find at the time)

You need to bring in your config somehow.  I use [Reflex](https://reflex.cold.org).  A sample config is available in `[config.json.in](config.json.in)`

Run as:

    ./jira-time-report < config.json

# build & deploy (docker)

Update `[docker-compose.yml](docker-compose.yml)` and `yourimagename` to suite your environment.

    docker-compose build
    docker push `yourimagename`:prd

Deploy to docker swarm:

    docker stack deploy -c docker-compose.yml jira-time

Note: this deploys with replicas:0.  This may seem counter-intuitive, but just setup a scheduled job that runs once a week and sets replicas=0, it'll run ones and close out.


# Todo:

* Get this running under one of the docker FaaS systems (Fusion, Foundry)
* Setup a backing store for stateful deltas of worklogs (incase somebody back-updates a work entry)
* Upload to other file stores (direct to google sheets would be sweet)

In all reality this should be just culling the jira information into a database that is shaped better for this need, and a separate web frontend exists to show the reports.  But that is more work.  This is a quick & dirty solution.

Enjoy!

