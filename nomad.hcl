job "timebot" {
    datacenters = ["home"]

    group "timebot" {
        count = 1

        restart {
            attempts    = 10
            interval    = "5m"
            delay       = "25s"
            mode        = "delay"
        }

        update {
            max_parallel = 1
            min_healthy_time = "10s"
            healthy_deadline = "3m"
            auto_revert = true
        }

        task "timebot" {
            driver = "docker"

            kill_timeout = "30s"

            config {
                mount {
                    type = "bind"
                    source = "local/config.ini"
                    target = "/app/config.ini"
                }

                image = "xnicare/timetablebot:1.0.5"
                network_mode = "host"
                volumes = [
                    "/opt/nomad/timebot/calendars:/app/calendars",
                    "/opt/nomad/timebot/downloads:/app/downloads",
                    "/opt/nomad/timebot/log:/app/log",
                    "/opt/nomad/timebot/timetable-dbs:/app/timetable-dbs",
                    "/opt/nomad/timebot/timetable-files:/app/timetable-files",
                    "/opt/nomad/timebot/dbs:/app/dbs"
                ]
            }

            resources {
                memory = 6144
            }

            template {
                data = <<EOH
{{ with nomadVar "nomad/jobs/timebot" }}
[MAIL]
imap_server={{ .imap_server }}
username={{ .mail_username }}
password={{ .mail_password }}

[VK]
group_id={{ .vk_group_id }}
group_token={{ .vk_group_token }}
group_token_2={{ .vk_group_token_2 }}

[GITHUB]
token={{ .github_token }}

[TELEGRAM]
tg_token={{ .tg_token }}

[DISCORD]
token={{ .discord_token }}

[TEST]
username={{ .test_username }}
password={{ .test_password }}
group_id={{ .test_group_id }}
group_token={{ .test_group_token }}
group_token2={{ .test_group_token2 }}
{{ end }}
EOH
                destination = "local/config.ini"
            }
        }
    }
}
