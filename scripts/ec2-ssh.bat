@echo off
ssh -i "D:\so\vms\mvp\infra\terraform\vms-dev.pem" -o StrictHostKeyChecking=no -t ubuntu@52.72.3.61 "$@"
