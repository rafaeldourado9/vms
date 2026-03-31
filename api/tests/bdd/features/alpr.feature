Feature: Detecção ALPR (Fluxo A — câmera inteligente)
  Como sistema VMS
  Preciso processar detecções ALPR de câmeras inteligentes
  Para registrar eventos de veículos identificados

  Background:
    Given um tenant "Acme" com slug "acme" existe
    And um usuário admin "admin@acme.com" com senha "senha12345" existe
    And eu estou autenticado como "admin@acme.com"
    And existe uma câmera "Cam ALPR" no meu tenant

  Scenario: Detecção ALPR cria evento
    When uma detecção ALPR com placa "ABC1234" e confiança 0.95 é recebida
    Then o evento é aceito
    And o evento aparece na listagem de eventos

  Scenario: Detecção duplicada é ignorada
    Given uma detecção ALPR com placa "DUP5678" já foi aceita
    When uma segunda detecção com placa "DUP5678" é recebida dentro do TTL
    Then a detecção é ignorada como duplicata

  Scenario: Fabricante não suportado retorna erro
    When uma detecção ALPR do fabricante "unknown_brand" é recebida
    Then eu recebo erro 400
