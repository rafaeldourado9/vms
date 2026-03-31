Feature: Edge Agent — Streaming e Heartbeat
  Como operador de segurança
  Preciso que o edge agent gerencie streams de câmeras
  Para ter vídeo ao vivo no VMS sem intervenção manual

  Background:
    Given um tenant "Acme" com slug "acme" existe
    And um usuário admin "admin@acme.com" com senha "senha12345" existe
    And eu estou autenticado como "admin@acme.com"

  Scenario: Agent faz heartbeat e recebe status online
    Given existe um agent "Agent Edge" no meu tenant com API key
    When o agent faz heartbeat com versão "1.0.0" e 2 streams rodando
    Then o agent fica com status "online"
    And o agent reporta versão "1.0.0"

  Scenario: Agent busca configuração e recebe câmeras ativas
    Given existe um agent "Agent Edge" no meu tenant com API key
    And existe uma câmera "Câmera 1" com URL RTSP "rtsp://cam1:554/live" no meu tenant
    When o agent busca sua configuração
    Then o agent recebe a lista de câmeras configuradas
    And a câmera "Câmera 1" está na lista de configuração

  Scenario: Agent com API key inválida não consegue fazer heartbeat
    When um agent faz heartbeat com API key "vms_invalid9999"
    Then eu recebo erro 401

  Scenario: Câmera desativada não aparece na configuração do agent
    Given existe um agent "Agent Edge" no meu tenant com API key
    And existe uma câmera inativa no meu tenant
    When o agent busca sua configuração
    Then a câmera inativa não aparece na lista de configuração
