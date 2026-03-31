Feature: Regras de Notificação
  Como administrador do VMS
  Preciso configurar regras de notificação
  Para receber webhooks quando eventos ocorrem

  Background:
    Given um tenant "Acme" com slug "acme" existe
    And um usuário admin "admin@acme.com" com senha "senha12345" existe
    And eu estou autenticado como "admin@acme.com"

  Scenario: Criar regra de notificação para ALPR
    When eu crio uma regra "Alerta ALPR" para eventos "alpr.*"
    Then a regra é criada com sucesso
    And a regra está ativa

  Scenario: Listar regras do tenant
    Given existe uma regra "Regra 1" para eventos "*"
    When eu listo as regras de notificação
    Then eu recebo pelo menos 1 regra na lista

  Scenario: Deletar regra de notificação
    Given existe uma regra "Regra Temp" para eventos "*"
    When eu deleto a regra
    Then a regra é removida com sucesso
