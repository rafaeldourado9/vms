Feature: Gerenciamento de Agents
  Como administrador do VMS
  Preciso criar e gerenciar agents
  Para que câmeras locais enviem streams ao MediaMTX

  Background:
    Given um tenant "Acme" com slug "acme" existe
    And um usuário admin "admin@acme.com" com senha "senha12345" existe
    And eu estou autenticado como "admin@acme.com"

  Scenario: Criar agent e receber API key
    When eu crio um agent "Agent Portaria"
    Then o agent é criado com sucesso
    And eu recebo uma API key que começa com "vms_"

  Scenario: Listar agents do tenant
    Given existe um agent "Agent 1" no meu tenant
    When eu listo os agents
    Then eu recebo pelo menos 1 agent na lista

  Scenario: Agent faz heartbeat via API key
    Given existe um agent "Agent HB" no meu tenant com API key
    When o agent faz heartbeat com versão "1.0.0" e 3 streams rodando
    Then o agent fica com status "online"
    And o agent reporta versão "1.0.0"

  Scenario: Agent busca configuração via API key
    Given existe um agent "Agent Config" no meu tenant com API key
    When o agent busca sua configuração
    Then o agent recebe a lista de câmeras configuradas

  Scenario: Heartbeat com API key inválida retorna 401
    When um agent faz heartbeat com API key "vms_invalid123"
    Then eu recebo erro 401
