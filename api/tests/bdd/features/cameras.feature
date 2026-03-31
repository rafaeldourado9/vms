Feature: Gerenciamento de Câmeras
  Como administrador do VMS
  Preciso criar e gerenciar câmeras
  Para monitorar os ambientes do meu tenant

  Background:
    Given um tenant "Acme" com slug "acme" existe
    And um usuário admin "admin@acme.com" com senha "senha12345" existe
    And eu estou autenticado como "admin@acme.com"

  Scenario: Criar câmera com dados válidos
    When eu crio uma câmera "Entrada Principal" com RTSP "rtsp://192.168.1.100:554/stream"
    Then a câmera é criada com sucesso
    And a câmera tem nome "Entrada Principal"
    And a câmera pertence ao meu tenant

  Scenario: Listar câmeras do tenant
    Given existe uma câmera "Cam 1" no meu tenant
    And existe uma câmera "Cam 2" no meu tenant
    When eu listo as câmeras
    Then eu recebo 2 câmeras na lista

  Scenario: Buscar câmera por ID
    Given existe uma câmera "Cam Portaria" no meu tenant
    When eu busco a câmera pelo ID
    Then eu recebo os dados da câmera "Cam Portaria"

  Scenario: Buscar câmera inexistente retorna 404
    When eu busco a câmera com ID "nonexistent"
    Then eu recebo erro 404

  Scenario: Deletar câmera
    Given existe uma câmera "Cam Temp" no meu tenant
    When eu deleto a câmera
    Then a câmera é removida com sucesso
