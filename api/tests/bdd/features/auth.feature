Feature: Autenticação de Usuários
  Como operador do VMS
  Preciso me autenticar com email e senha
  Para acessar os recursos protegidos da API

  Background:
    Given um tenant "Acme" com slug "acme" existe
    And um usuário admin "admin@acme.com" com senha "senha12345" existe

  Scenario: Login com credenciais válidas
    When eu faço login com email "admin@acme.com" e senha "senha12345"
    Then eu recebo um access token válido
    And eu recebo um refresh token válido

  Scenario: Login com senha incorreta
    When eu faço login com email "admin@acme.com" e senha "errada123"
    Then eu recebo erro 401

  Scenario: Login com email inexistente
    When eu faço login com email "nobody@acme.com" e senha "senha12345"
    Then eu recebo erro 401

  Scenario: Refresh de token
    Given eu estou autenticado como "admin@acme.com"
    When eu renovo meu token com o refresh token
    Then eu recebo um novo access token
    And eu recebo um novo refresh token

  Scenario: Acessar recurso protegido sem token
    When eu acesso GET "/api/v1/users/me" sem token
    Then eu recebo erro 401

  Scenario: Acessar recurso protegido com token válido
    Given eu estou autenticado como "admin@acme.com"
    When eu acesso GET "/api/v1/users/me" com meu token
    Then eu recebo os dados do usuário "admin@acme.com"
