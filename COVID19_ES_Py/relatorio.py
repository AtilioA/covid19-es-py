"""O módulo `relatorio.py` é o principal do pacote a partir de 15/04/2020 (`COVID19-ES-Py 2.0.0`).
Nele são introduzidas as classes e métodos utilizados para coletar dados dos relatórios emitidos pelo Governo através do painel PowerBI.

"""

from functools import total_ordering
import copy

from pathlib import Path
from io import BytesIO
import requests
import rows
import arrow

from .utils import MUNICIPIOS, remove_caracteres_especiais, trata_dados_linha
from .exceptions import RelatorioError

# URL direta para o arquivo csv dos microdados do painel PowerBI
URL_RELATORIO_CSV = "https://bi.static.es.gov.br/covid19/MICRODADOS.csv"


@total_ordering
class Municipio():
    """
    Um objeto `Municipio` representa um município do estado do Espírito Santo.

    Parameters
    ----------
    Nome : ``str``
        O nome do município a ser atribuído ao objeto.

    Attributes
    ----------
    nome : ``str``
        O nome do município.
    casos : ``list`` : ``Caso``
        Uma lista de objetos do tipo Caso.
    casosConfirmados : ``int``
        O número de casos confirmados no município.
    obitos : ``int``
        O número de óbitos confirmados em decorrência de COVID-19 no município.
    """

    def __init__(self, nome):
        self.nome = nome
        self.casos = []
        self.casosConfirmados = 0
        self.obitos = 0

    # Objetos do tipo Municipio podem ser comparados alfabeticamente
    def __eq__(self, other):
        return (self.nome.lower() == other.nome.lower())

    def __lt__(self, other):
        return (self.nome.lower() < other.nome.lower())

    def __str__(self):
        return f"Município {self.nome}:\n{self.casosConfirmados} casos confirmados.\n{self.obitos} óbitos."

    def __repr__(self):
        return f"{{'casosConfirmados': {self.casosConfirmados}, 'obitos': {self.obitos}}}"


class Caso():
    """
    Um objeto `Caso` é capaz de abstrair o registro de um caso lido do csv.

    Parameters
    ----------
    dados : ``iterable``
        Um iterável com os dados do caso.

    Attributes
    ----------
    data : Objeto `arrow`
        A data de registro do caso.
    classificacao : ``str``
        A classificação da ocorrência de COVID-19 no paciente.
    evolucao : ``str`` ou ``None``
        A evolução da situação do paciente ou None se não for informada.
    criterioConfirmacao : ``str`` ou ``None``
        O critério usado para a classificação do caso ou None se não for informada.
    statusNotificacao : ``str``
        O estado atual do caso.
    municipio : ``str``
        O município de origem do paciente.
    bairro : ``str`` ou ``None``
        O bairro de origem do paciente.
    faixaEtaria : ``str``
        A faixa etária do paciente.
    sexo : ``str``
        O sexo do paciente.
    racaCor : ``str`` ou ``None``
        A raça/cor do paciente ou None se não for informada.
    escolaridade : ``str``
        O grau de escolaridade do paciente ou ``None`` se não for informada.
    sintomas : ``dict`` : ``bool``
        Os sintomas apresentados pelo paciente.
    comorbidades : ``dict`` : ``bool``
        As comorbidades apresentadas pelo paciente.
    ficouInternado : ``bool`` ou ``None``
        Se o paciente ficou internado ou não.
    viagemBrasil : ``bool`` ou ``None``
        Se o paciente realizou viagem nacional ou não.
    viagemInternacional : ``bool`` ou ``None``
        Se o paciente realizou viagem internacional ou não.
    """

    def __init__(self,
                 dados=None,
                 data=None,
                 classificacao=None,
                 evolucao=None,
                 criterioConfirmacao=None,
                 statusNotificacao=None,
                 municipio=None,
                 bairro=None,
                 faixaEtaria=None,
                 sexo=None,
                 racaCor=None,
                 escolaridade=None,
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
            self.criterioConfirmacao = criterioConfirmacao
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
        """Carrega os dados presentes em uma linha do csv para o objeto Caso.
        Retorna o objeto Caso preenchido.
        """

        linha = trata_dados_linha(list(linha))

        self.data = linha[0]
        self.classificacao = linha[1]
        self.evolucao = linha[2]
        self.criterioConfirmacao = linha[3]
        self.statusNotificacao = linha[4]
        self.municipio = linha[5]
        self.bairro = linha[6]
        self.faixaEtaria = linha[7]
        self.sexo = linha[8]
        self.racaCor = linha[9]
        self.escolaridade = linha[10]
        self.sintomas = {
            "febre": linha[11],
            "dificuldadeRespiratoria": linha[12],
            "tosse": linha[13],
            "coriza": linha[14],
            "dorGarganta": linha[15],
            "diarreia": linha[16],
            "cefaleia": linha[17],
        }
        self.comorbidades = {
            "comorbidadePulmao": linha[18],
            "comorbidadeCardio": linha[19],
            "comorbidadeRenal": linha[20],
            "comorbidadeDiabetes": linha[21],
            "comorbidadeTabagismo": linha[22],
            "comorbidadeObesidade": linha[23]
        }
        self.ficouInternado = linha[24]
        self.viagemBrasil = linha[25]
        self.viagemInternacional = linha[26]

        return self


class Relatorio():
    """
    Um objeto `Relatorio` é capaz de abstrair um relatório em csv emitido pelo painel PowerBI.

    Parameters
    ----------
    caminhoCSV : ``string``
        Caminho até o arquivo csv. Se não for informado, baixa do PowerBI.

    Attributes
    ----------
    csv : ``str``
        A string com caminho ou URL do arquivo csv.
    linhasRelatorio : ``list`` : ``Row``
        A lista de objetos Row lidos do arquivo csv.
    casosMunicipios : ``dict`` : ``Municipio``
        O dicionário de objetos Municipio
    importadosOuIndefinidos : ``dict`` : ``int``
        O dicionário com total de casos confirmados e óbitos de municípios indefinidos ou de pacientes de fora do ES.
    totalGeral : ``dict`` : ``int``
        O dicionário com total de casos confirmados e óbitos no ES.
    nMunicipiosInfectados : ``int``
        O número de municípios infectados deste relatório.
    """

    def __init__(self, caminhoCSV=None):
        if caminhoCSV:
            self.csv = Path(caminhoCSV)
            self.linhasRelatorio = rows.import_from_csv(self.csv, encoding='ANSI')
        else:
            self.csv = URL_RELATORIO_CSV
            self.linhasRelatorio = None

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
        """Inicializa o dicionário de municípios do Relatorio."""

        for municipio in MUNICIPIOS:
            self.casosMunicipios[municipio] = Municipio(municipio)

    def busca_casos_municipio(self, municipio):
        """Realiza pesquisa no Relatorio por casos registrados em um município.

        Parameters
        ----------
        municipio : ``str``
            O município a ser pesquisado.

        Raises
        ----------
        `RelatorioError`
            Se o município não for encontrado na lista de casos.

        Returns
        ----------
        self.casos[municipio] : ``dict``
            O dicionário de casos registrados no município."""

        stringMunicipioTratada = remove_caracteres_especiais(
            municipio).upper().strip()
        try:
            return self.casosMunicipios[stringMunicipioTratada]
        except KeyError:
            raise RelatorioError(
                f"O município '{municipio}' não foi encontrado no relatório. Pode ter ocorrido um erro de digitação ou o município não registrou casos de COVID-19.")

    def popula_relatorio(self):
        """Preenche o Relatorio com as informações presentes em self.linhasRelatorio e retorna uma cópia do Relatorio."""

        self.totalGeral['casosConfirmados'] = 0
        self.totalGeral['obitos'] = 0
        self.inicializa_dicionario_municipios()
        self.nMunicipiosInfectados = 0
        self.importadosOuIndefinidos['casosConfirmados'] = 0
        self.importadosOuIndefinidos['obitos'] = 0

        for linha in self.linhasRelatorio:
            caso = Caso(linha)
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
        return copy.copy(self)

    def __str__(self):
        return f"Relatório do arquivo {self.csv}:\nTotal geral: {self.totalGeral}\n{self.nMunicipiosInfectados} municípios infectados."


class LeitorRelatorio():
    """
    Um objeto `LeitorRelatorio` é capaz de manipular relatórios emitidos pelo painel PowerBI.

    Parameters
    ----------
    caminhoCSV : ``string``
        Caminho até o arquivo csv. Se não for informado, baixa do PowerBI.

    Attributes
    ----------
    csv : ``str``
        A string com caminho ou URL do arquivo csv.
    linhasRelatorio : ``list`` : ``Row``
        A lista de objetos Row lidos do arquivo csv.
    relatorio : ``Relatorio``
        O objeto Relatorio criado a partir do csv
        O número de municípios infectados deste relatório.
    """

    def __init__(self, caminhoCSV=None):
        self.relatorio = Relatorio()
        if caminhoCSV:
            self.csv = Path(caminhoCSV)
            self.linhasRelatorio = rows.import_from_csv(self.csv, encoding='ANSI')
            self.relatorio.csv = self.csv
            self.relatorio.linhasRelatorio = self.linhasRelatorio
            self.relatorio.popula_relatorio()
        else:
            self.csv = URL_RELATORIO_CSV

    def carrega_ultimo_relatorio(self):
        """Baixa e lê o arquivo csv mais recente do PowerBI."""

        self.relatorio.csv = URL_RELATORIO_CSV
        self.linhasRelatorio = rows.import_from_csv(
            BytesIO(requests.get(self.relatorio.csv).content), encoding='ANSI')
        self.relatorio.linhasRelatorio = self.linhasRelatorio

        return self.relatorio.popula_relatorio()

    def filtra_casos_ate_dia(self, data):
        """Filtra relatório por casos até o dia fornecido (incluso).

        Parameters
        ----------
        data : ``str``
            A data limite (incluso) a ser usada como filtro.
            Formatos de data aceitos:
            "DD/MM/YYYY", "DD-MM-YYYY", "DD_MM_YYYY", "DD.MM.YYYY", "DDMMYYYY".

        Returns
        ----------
        Relatorio : `Relatorio`
            O Relatorio filtrado e preenchido com os registros até a data especificada.
        """

        if self.relatorio.linhasRelatorio:
            dataArrow = arrow.get(
                data, ["DD/MM/YYYY", "DD-MM-YYYY", "DD_MM_YYYY", "DD.MM.YYYY", "DDMMYYYY"]
            )
            self.relatorio.linhasRelatorio = [
                caso for caso in self.linhasRelatorio[1:] if dataArrow >= arrow.get(caso[0], ["DD/MM/YYYY", "DD-MM-YYYY", "DD_MM_YYYY", "DD.MM.YYYY", "DDMMYYYY"])
            ]
            return self.relatorio.popula_relatorio()
        else:
            raise RelatorioError(
                "Não é possível filtrar pois o relatório está vazio (use o método popula_relatorio() para preencher o relatório).")

    def filtra_casos_no_dia(self, data):
        """Filtra relatório por casos no dia fornecido.

        Parameters
        ----------
        data : ``str``
            A data específica a ser pesquisada.
            Formatos de data aceitos:
            "DD/MM/YYYY", "DD-MM-YYYY", "DD_MM_YYYY", "DD.MM.YYYY", "DDMMYYYY".

        Returns
        ----------
        Relatorio : `Relatorio`
            O Relatorio filtrado e preenchido com os registros da data especificada.
        """

        if self.relatorio.linhasRelatorio:
            dataArrow = arrow.get(
                data, ["DD/MM/YYYY", "DD-MM-YYYY", "DD_MM_YYYY", "DD.MM.YYYY", "DDMMYYYY"]
            )
            self.relatorio.linhasRelatorio = [
                caso for caso in self.linhasRelatorio[1:] if dataArrow == arrow.get(caso[0], ["DD/MM/YYYY", "DD-MM-YYYY", "DD_MM_YYYY", "DD.MM.YYYY", "DDMMYYYY"])
            ]
            return self.relatorio.popula_relatorio()
        else:
            raise RelatorioError(
                "Não é possível filtrar pois o relatório está vazio (use o método popula_relatorio() para preencher o relatório).")

    def __str__(self):
        if self.csv:
            return f"Leitor de relatórios carregado com {self.csv}."
        else:
            return f"Leitor de relatórios sem dados para ler."
