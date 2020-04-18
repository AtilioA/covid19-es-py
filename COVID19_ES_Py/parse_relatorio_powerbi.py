from functools import total_ordering

from io import BytesIO
import requests
import rows
import arrow

from COVID19_ES_Py.utils import MUNICIPIOS, remove_caracteres_especiais

URL_RELATORIO_CSV = "https://bi.static.es.gov.br/covid19/MICRODADOS.csv"


def trata_dados_linha(linha):
    linha[0] = arrow.get(linha[0], 'DD/MM/YYYY')

    if linha[2] in ["Ignorado", "-"]:
        linha[2] = None
    if "-" in linha[3]:
        linha[3] = None
    if linha[6] in ["Não encontrado", "NULL"]:
        linha[6] = None
    if "Ignorado" in linha[9]:
        linha[9] = None
    if "Ignorado" in linha[10]:
        linha[10] = None
    if "-" in linha[11]:
        linha[11] = None

    stringParaBool = {
        "Sim": True,
        "Não": False,
        "-": None,
        "": None,
        1: True,
        2: None,
    }
    for i, campo in enumerate(linha[12:]):
        linha[i + 12] = stringParaBool.get(linha[i + 12], None)

    return linha


@total_ordering
class Municipio():
    def __init__(self, nome):
        self.nome = nome
        self.casos = []
        self.casosConfirmados = 0
        self.obitos = 0

    def __eq__(self, other):
        return (self.nome.lower() == other.nome.lower())

    def __lt__(self, other):
        return (self.nome.lower() < other.nome.lower())


class Caso():
    def __init__(self,
                 dados=None,
                 data=None,
                 faixaEtaria=None,
                 sexo=None,
                 racaCor=None,
                 escolaridade=None,
                 classificacao=None,
                 evolucao=None,
                 criterioClassificacao=None,
                 statusNotificacao=None,
                 municipio=None,
                 bairro=None,
                 sintomas=None,
                 comorbidades=None,
                 ficouInternado=None,
                 viagemBrasil=None,
                 viagemInternacional=None):
        if dados:
            self.carrega_dados_linha(dados)
        else:
            self.data = data
            self.classificacao = classificacao
            self.evolucao = evolucao
            self.criterioClassificacao = criterioClassificacao
            self.statusNotificacao = statusNotificacao
            self.municipio = municipio
            self.bairro = bairro
            self.faixaEtaria = faixaEtaria
            self.sexo = sexo
            self.racaCor = racaCor
            self.escolaridade = escolaridade
            self.sintomas = sintomas
            self.comorbidades = comorbidades
            self.ficouInternado = ficouInternado
            self.viagemBrasil = viagemBrasil
            self.viagemInternacional = viagemInternacional

    def __str__(self):
        return f"Caso de {self.data} - {self.classificacao} em {self.municipio}"

    def carrega_dados_linha(self, linha):
        linha = trata_dados_linha(list(linha))

        self.data = linha[0]
        self.classificacao = linha[1]
        self.evolucao = linha[2]
        self.criterioClassificacao = linha[3]
        self.statusNotificacao = linha[4]
        self.municipio = linha[5]
        self.bairro = linha[6]
        self.faixaEtaria = linha[7]
        self.sexo = linha[8]
        self.racaCor = linha[9]
        self.escolaridade = linha[10]
        self.sintomas = {
            "cefaleia": linha[11],
            "coriza": linha[12],
            "diarreia": linha[13],
            "dificuldadeRespiratoria": linha[14],
            "dorGarganta": linha[15],
            "febre": linha[16],
            "tosse": linha[17]
        }
        self.comorbidades = {
            "comorbidadeCardio": linha[18],
            "comorbidadeDiabetes": linha[19],
            "comorbidadePulmao": linha[20],
            "comorbidadeRenal": linha[21],
            "comorbidadeTabagismo": linha[22],
            "comorbidadeObesidade": linha[23]
        }
        self.ficouInternado = linha[24]
        self.viagemBrasil = linha[25]
        self.viagemInternacional = linha[26]


class Relatorio():
    def __init__(self, caminhoCSV=None):
        if caminhoCSV:
            self.csv = caminhoCSV
            self.rows = rows.import_from_csv(self.csv)
        else:
            self.csv = URL_RELATORIO_CSV
            self.rows = rows.import_from_csv(BytesIO(requests.get(self.csv).content))

        self.casosMunicipios = {}
        self.inicializa_dicionario_municipios()
        self.importadosOuIndefinidos = {
            'casosConfirmados': 0,
            'obitos': 0
        }

        self.totalGeral = {
            'casosConfirmados': 0,
            'obitos': 0
        }
        self.nMunicipiosInfectados = 0

    def inicializa_dicionario_municipios(self):
        for municipio in MUNICIPIOS:
            self.casosMunicipios[municipio] = Municipio(municipio)

    def filtra_data(self, data):
        dataArrow = arrow.get(data, "DD/MM/YYYY")

        return [caso for caso in self.rows[1:] if dataArrow >= arrow.get(caso[0], "DD/MM/YYYY") and "Confirmados" in caso[1]]

    def popula_relatorio(self):
        for linha in self.rows:
            caso = Caso(linha)
            if caso.classificacao == "Confirmados":
                if remove_caracteres_especiais(caso.municipio.upper()) in MUNICIPIOS:
                    if self.casosMunicipios[caso.municipio].casosConfirmados == 0:
                        self.nMunicipiosInfectados += 1
                    if (caso.evolucao == "Óbito pelo COVID-19"):
                        self.totalGeral['obitos'] += 1
                        self.casosMunicipios[caso.municipio].obitos += 1
                    self.casosMunicipios[caso.municipio].casos.append(caso)
                    self.casosMunicipios[caso.municipio].casosConfirmados += 1
                else:
                    self.importadosOuIndefinidos['casosConfirmados'] += 1
                    if (caso.evolucao == "Óbito pelo COVID-19"):
                        self.totalGeral['obitos'] += 1
                        self.importadosOuIndefinidos['obitos'] += 1

                self.totalGeral['casosConfirmados'] += 1
                print(self)

    def __str__(self):
        return f"Relatório do arquivo {self.csv}:\nTotal geral: {self.totalGeral}\n{self.nMunicipiosInfectados} municípios infectados."


