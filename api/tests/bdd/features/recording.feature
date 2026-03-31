Feature: Gravações e Clipes
  Como operador do VMS
  Preciso acessar segmentos de gravação e solicitar clipes
  Para revisar eventos de segurança

  Background:
    Given um tenant "Acme" com slug "acme" existe
    And um usuário admin "admin@acme.com" com senha "senha12345" existe
    And eu estou autenticado como "admin@acme.com"
    And existe uma câmera "Cam Gravação" no meu tenant

  Scenario: Listar segmentos de uma câmera sem gravações
    When eu listo os segmentos da câmera
    Then eu recebo lista vazia de segmentos

  Scenario: Solicitar clipe de vídeo
    When eu solicito um clipe dos últimos 5 minutos
    Then o clipe é criado com status "pending"
    And o clipe pertence à câmera correta

  Scenario: Listar clipes do tenant
    Given eu solicitei um clipe dos últimos 5 minutos
    When eu listo os clipes
    Then eu recebo pelo menos 1 clipe na lista
