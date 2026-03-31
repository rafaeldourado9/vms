Feature: Analytics — Ingestão e ROIs via API
  Como sistema VMS com analytics server-side
  Preciso ingerir resultados de analytics e gerenciar ROIs
  Para processar eventos de câmeras baratas com IA

  Background:
    Given um tenant "Acme" com slug "acme" existe
    And um usuário admin "admin@acme.com" com senha "senha12345" existe
    And eu estou autenticado como "admin@acme.com"
    And existe uma câmera "Cam Analytics" no meu tenant

  Scenario: Criar ROI de intrusão para câmera
    When eu crio uma ROI "Zona Proibida" do tipo "intrusion" para a câmera
    Then a ROI é criada com sucesso
    And a ROI tem tipo "intrusion"

  Scenario: Ingestão de resultado de analytics cria evento
    When o analytics_service envia um resultado de intrusão para a câmera
    Then o resultado é aceito com status 201

  Scenario: Listar ROIs do tenant
    Given existe uma ROI "Entrada" do tipo "human_traffic" para a câmera
    When eu listo as ROIs do tenant
    Then eu recebo pelo menos 1 ROI na lista
