@echo off
REM Script para testar login no VMS
curl -sk -X POST "https://vms-server.duckdns.org/api/v1/auth/token" ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"admin@vms.com\",\"password\":\"admin123\"}"
