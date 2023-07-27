job "timebot" {
    datacenters = ["timeweb-ru"]

    group "timebot" {
        count = 1

        restart {
            attempts    = 10
            interval    = "5m"
            delay       = "25s"
            mode        = "delay"
        }

        task "timebot" {
            driver = "docker"

            config {
                mount {
                    type = "bind"
                    source = "config"
                    target = "/app/config.ini"
                }

                image = "xnicare/timetablebot:latest"
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
                memory = 600
            }

            template {
                data        = <<EOH
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
                destination = "config"
            }
        }
    }
}