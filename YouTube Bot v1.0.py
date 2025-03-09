"""
AI PRO Revolution - YouTube Live Bot v1.0
Connects YouTube Live Chat with OpenAI's Assistants API.
Developed by Thiago Caliman
"""
import os
import time
import json
import logging
import argparse
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from openai import OpenAI

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("janete_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("JaneteBot")

# Constantes e configurações padrão
VERSION = "1.0.0"
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'
CONFIG_FILE = 'config.json'
DEFAULT_INTERVAL = 10  # Intervalo padrão aumentado para 10 segundos para economizar cota
MAX_MESSAGES_MEMORY = 500  # Quantidade de mensagens para manter em memória
QUOTA_RESERVE = 1000  # Reserva de cota para garantir funcionamento até o final da transmissão
MAX_MESSAGE_LENGTH = 200  # Tamanho máximo de mensagem no chat do YouTube

class JaneteBot:
    def __init__(self):
        """Inicializa o bot com configurações padrão ou do arquivo config.json."""
        self.config = self._load_config()
        self.youtube = None
        self.openai_client = None
        self.live_chat_id = None
        self.next_page_token = None
        self.mensagens_processadas = set()
        self.id_ultima_mensagem_bot = None
        self.quota_usage = 0
        self.last_message_time = time.time()
        self.bot_running = False
        
        # Contadores para estatísticas
        self.stats = {
            "messages_received": 0,
            "messages_responded": 0,
            "api_calls": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None
        }

    def _load_config(self):
        """Carrega configurações do arquivo config.json ou usa padrões."""
        default_config = {
            "nome_bot": "Janete",
            "id_transmissao": "",
            "id_assistente": "",
            "nome_canal_bot": "",
            "intervalo_verificacao": DEFAULT_INTERVAL,
            "modo_economia": False,
            "intervalo_economia": 20,
            "cota_diaria": 10000
        }
        
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Mesclar com os padrões para garantir que todos os campos existam
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    logger.info(f"Configurações carregadas de {CONFIG_FILE}")
                    return config
            else:
                logger.warning(f"Arquivo {CONFIG_FILE} não encontrado. Usando configurações padrão.")
                return default_config
        except Exception as e:
            logger.error(f"Erro ao carregar configurações: {e}")
            return default_config
    
    def _save_config(self):
        """Salva as configurações atuais no arquivo config.json."""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Configurações salvas em {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}")
    
    def _setup_quota_tracking(self):
        """Configura o rastreamento de cota, criando ou lendo o arquivo de uso."""
        today = datetime.now().strftime('%Y-%m-%d')
        quota_file = 'quota_usage.json'
        
        if os.path.exists(quota_file):
            try:
                with open(quota_file, 'r') as f:
                    quota_data = json.load(f)
                    if quota_data.get('date') == today:
                        self.quota_usage = quota_data.get('usage', 0)
                        logger.info(f"Uso de cota hoje: {self.quota_usage}/{self.config['cota_diaria']} unidades")
                    else:
                        # Novo dia, resetar o contador
                        self.quota_usage = 0
                        logger.info("Novo dia, contador de cota resetado")
            except Exception as e:
                logger.error(f"Erro ao ler arquivo de cota: {e}")
                self.quota_usage = 0
        else:
            self.quota_usage = 0
            logger.info("Iniciando rastreamento de uso de cota")
    
    def _update_quota_usage(self, units):
        """Atualiza o uso de cota e salva no arquivo."""
        self.quota_usage += units
        today = datetime.now().strftime('%Y-%m-%d')
        quota_data = {
            'date': today,
            'usage': self.quota_usage
        }
        
        try:
            with open('quota_usage.json', 'w') as f:
                json.dump(quota_data, f)
        except Exception as e:
            logger.error(f"Erro ao salvar uso de cota: {e}")
        
        # Verificar se estamos próximos do limite
        if self.quota_usage > (self.config['cota_diaria'] - QUOTA_RESERVE) and not self.config['modo_economia']:
            logger.warning(f"ALERTA DE COTA: {self.quota_usage}/{self.config['cota_diaria']} unidades usadas!")
            logger.warning("Ativando modo de economia de cota!")
            self.config['modo_economia'] = True
            self._save_config()
    
    def setup(self, args):
        """Configura o bot com base nos argumentos da linha de comando."""
        # Sobreescrever configurações com argumentos da linha de comando
        if args.transmissao:
            self.config['id_transmissao'] = args.transmissao
            logger.info(f"ID da transmissão definido via argumento: {args.transmissao}")
        
        if args.intervalo:
            self.config['intervalo_verificacao'] = args.intervalo
            logger.info(f"Intervalo definido via argumento: {args.intervalo}")
        
        if args.economia:
            self.config['modo_economia'] = True
            logger.info("Modo de economia ativado via argumento")
        
        # Verificar se há ID de transmissão
        if not self.config['id_transmissao']:
            logger.error("ID da transmissão não definido!")
            return False
        
        # Configurar rastreamento de cota
        self._setup_quota_tracking()
        
        # Salvar configuração atualizada
        self._save_config()
        return True
    
    def autenticar_youtube(self):
        """Autentica com a API do YouTube."""
        try:
            if not os.path.exists('client_secret.json'):
                logger.error("Arquivo client_secret.json não encontrado!")
                logger.info("1. Acesse https://console.cloud.google.com/")
                logger.info("2. Crie um projeto e ative a API do YouTube")
                logger.info("3. Em 'Credenciais', crie uma credencial OAuth")
                logger.info("4. Baixe o arquivo JSON e renomeie para 'client_secret.json'")
                return False
                
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret.json', SCOPES)
            credentials = flow.run_local_server(port=0)
            
            self.youtube = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)
            logger.info("Autenticação no YouTube concluída!")
            return True
        except Exception as e:
            logger.error(f"Erro ao autenticar no YouTube: {e}")
            return False
    
    def autenticar_openai(self):
        """Autentica com a API da OpenAI."""
        try:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                logger.error("Chave da API da OpenAI não encontrada!")
                logger.info("Defina a variável de ambiente OPENAI_API_KEY.")
                logger.info("  No Windows: set OPENAI_API_KEY=sua-chave-api")
                logger.info("  No Linux/Mac: export OPENAI_API_KEY=sua-chave-api")
                return False
            
            self.openai_client = OpenAI(api_key=api_key)
            
            # Verificar assistente
            if not self.config['id_assistente']:
                logger.error("ID do assistente não configurado!")
                return False
            
            assistente = self.openai_client.beta.assistants.retrieve(self.config['id_assistente'])
            logger.info(f"Assistente encontrado: {assistente.name}")
            return True
        except Exception as e:
            logger.error(f"Erro ao autenticar na OpenAI: {e}")
            return False
    
    def obter_live_chat_id(self):
        """Obtém o ID do chat ao vivo da transmissão configurada."""
        try:
            logger.info(f"Buscando detalhes para o vídeo ID: {self.config['id_transmissao']}")
            self._update_quota_usage(1)  # videos.list custa 1 unidade
            
            request = self.youtube.videos().list(
                part="liveStreamingDetails,snippet",
                id=self.config['id_transmissao']
            )
            response = request.execute()
            
            if not response.get('items'):
                logger.error(f"Nenhum vídeo encontrado com o ID: {self.config['id_transmissao']}")
                return False
            
            title = response['items'][0].get('snippet', {}).get('title', 'Sem título')
            logger.info(f"Vídeo encontrado: {title}")
            
            # Verificar se há detalhes de transmissão ao vivo
            if 'liveStreamingDetails' not in response['items'][0]:
                logger.error("Este vídeo não é uma transmissão ao vivo!")
                return False
                
            self.live_chat_id = response['items'][0]['liveStreamingDetails'].get('activeLiveChatId')
            
            if not self.live_chat_id:
                logger.error("Chat ao vivo não disponível para este vídeo!")
                return False
                
            logger.info(f"ID do chat ao vivo obtido: {self.live_chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao obter ID do chat: {e}")
            return False
    
    def obter_mensagens_chat(self):
        """Obtém as mensagens do chat ao vivo."""
        try:
            self._update_quota_usage(5)  # liveChatMessages.list custa ~5 unidades
            self.stats["api_calls"] += 1
            
            request = self.youtube.liveChatMessages().list(
                liveChatId=self.live_chat_id,
                part="snippet,authorDetails",
                pageToken=self.next_page_token
            )
            return request.execute()
        except HttpError as e:
            if "quota" in str(e).lower():
                logger.error("ERRO DE COTA: Limite de cota da API do YouTube excedido!")
                logger.info("Aguarde até amanhã ou solicite um aumento de cota em console.cloud.google.com")
                return {"items": []}
            else:
                logger.error(f"Erro HTTP ao obter mensagens: {e}")
                return {"items": []}
        except Exception as e:
            logger.error(f"Erro ao obter mensagens: {e}")
            return {"items": []}
    
    def enviar_mensagem_chat(self, mensagem):
        """Envia uma mensagem para o chat ao vivo."""
        try:
            # Limitar o tamanho da mensagem para evitar erros da API
            if len(mensagem) > MAX_MESSAGE_LENGTH:
                mensagem = mensagem[:MAX_MESSAGE_LENGTH-3] + "..."
                
            self._update_quota_usage(50)  # liveChatMessages.insert custa ~50 unidades
            self.stats["api_calls"] += 1
            
            request = self.youtube.liveChatMessages().insert(
                part="snippet",
                body={
                    "snippet": {
                        "liveChatId": self.live_chat_id,
                        "type": "textMessageEvent",
                        "textMessageDetails": {
                            "messageText": mensagem
                        }
                    }
                }
            )
            return request.execute()
        except HttpError as e:
            if "quota" in str(e).lower():
                logger.error("ERRO DE COTA: Limite de cota da API do YouTube excedido!")
                return None
            else:
                logger.error(f"Erro HTTP ao enviar mensagem: {e}")
                self.stats["errors"] += 1
                return None
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}")
            self.stats["errors"] += 1
            return None
    
    def obter_resposta_assistente(self, pergunta):
        """Obtém uma resposta do Assistente da OpenAI."""
        try:
            # Cria um thread
            thread = self.openai_client.beta.threads.create()
            
            # Adiciona a mensagem ao thread
            self.openai_client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=pergunta
            )
            
            # Executa o assistente no thread
            run = self.openai_client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.config['id_assistente']
            )
            
            # Verifica o status da execução
            while run.status != "completed":
                run = self.openai_client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )
                
                if run.status == "failed":
                    logger.error(f"Execução do assistente falhou: {run.last_error}")
                    return "Desculpe, tive um problema ao processar sua pergunta."
                
                if run.status == "expired":
                    logger.error("Execução do assistente expirou")
                    return "Desculpe, o tempo de resposta expirou. Tente novamente."
                
                # Aguarda um pouco antes de verificar novamente
                time.sleep(1)
            
            # Recupera as mensagens do thread
            messages = self.openai_client.beta.threads.messages.list(
                thread_id=thread.id
            )
            
            # Obtém a última resposta do assistente
            for message in messages.data:
                if message.role == "assistant":
                    # Retorna apenas o conteúdo textual
                    text_content = ""
                    for content in message.content:
                        if content.type == "text":
                            text_content += content.text.value
                    
                    # Limita o tamanho para o chat
                    if len(text_content) > MAX_MESSAGE_LENGTH:
                        text_content = text_content[:MAX_MESSAGE_LENGTH-3] + "..."
                    
                    return text_content
            
            return "Não consegui gerar uma resposta para sua pergunta."
        
        except Exception as e:
            logger.error(f"Erro ao obter resposta do assistente: {e}")
            self.stats["errors"] += 1
            return "Desculpe, ocorreu um erro ao processar sua pergunta."
    
    def extrair_nome_usuario(self, nome_completo):
        """Extrai um nome de usuário mais curto do nome completo."""
        # Se o nome tiver um pipe, pega apenas o que vem antes
        if "|" in nome_completo:
            partes = nome_completo.split("|")
            return partes[0].strip()
        
        # Se for um nome muito longo, tenta dividir por espaços
        if len(nome_completo) > 20:
            partes = nome_completo.split()
            if len(partes) > 1:
                # Retorna o primeiro nome ou os dois primeiros nomes
                return " ".join(partes[:2])
        
        # Caso contrário, retorna o nome completo
        return nome_completo
    
    def monitorar_chat(self):
        """Monitora o chat ao vivo e responde quando o bot é mencionado."""
        self.bot_running = True
        self.stats["start_time"] = datetime.now()
        
        intervalo_atual = self.config['intervalo_verificacao']
        if self.config['modo_economia']:
            intervalo_atual = self.config['intervalo_economia']
            logger.info(f"Modo economia ativado! Intervalo: {intervalo_atual}s")
        else:
            logger.info(f"Intervalo entre verificações: {intervalo_atual}s")
        
        logger.info("💬 Monitoramento do chat iniciado")
        logger.info(f"📢 O bot '{self.config['nome_bot']}' responderá quando for mencionado no chat")
        logger.info("📢 Também responderá a mensagens iniciadas com '!'")
        logger.info("📢 As perguntas serão encaminhadas para o Assistente da OpenAI")
        logger.info("📢 Pressione Ctrl+C para encerrar")
        
        try:
            while self.bot_running:
                # Verificar se é hora de verificar o chat (baseado no intervalo)
                tempo_atual = time.time()
                if tempo_atual - self.last_message_time < intervalo_atual:
                    time.sleep(0.5)  # Pequena pausa para não consumir CPU
                    continue
                
                # Atualizar timestamp da última verificação
                self.last_message_time = tempo_atual
                
                # Verificar se estamos próximos do limite de cota
                if self.config['modo_economia']:
                    intervalo_atual = self.config['intervalo_economia']
                else:
                    intervalo_atual = self.config['intervalo_verificacao']
                
                # Obter novas mensagens
                resposta_chat = self.obter_mensagens_chat()
                self.next_page_token = resposta_chat.get('nextPageToken')
                
                # Processar novas mensagens
                for mensagem in resposta_chat.get('items', []):
                    id_mensagem = mensagem['id']
                    
                    # Pular mensagens já processadas
                    if id_mensagem in self.mensagens_processadas:
                        continue
                    
                    self.mensagens_processadas.add(id_mensagem)
                    self.stats["messages_received"] += 1
                    
                    # Dados da mensagem
                    nome_autor = mensagem['authorDetails']['displayName']
                    texto_mensagem = mensagem['snippet']['displayMessage']
                    
                    # Verificar se é uma mensagem do próprio bot (para evitar loops)
                    if nome_autor == self.config['nome_canal_bot']:
                        self.id_ultima_mensagem_bot = id_mensagem
                        continue
                    
                    # Verificar se a mensagem está respondendo ao bot (começa com @)
                    if texto_mensagem.startswith("@"):
                        # Ignorar respostas às mensagens do bot para evitar loops
                        continue
                    
                    logger.info(f"💬 {nome_autor}: {texto_mensagem}")
                    
                    # Verificar se o bot foi mencionado ou comando iniciado com !
                    if self.config['nome_bot'].lower() in texto_mensagem.lower() or texto_mensagem.startswith('!'):
                        # Se a mensagem começar com '!', remover o '!' para processamento
                        pergunta = texto_mensagem
                        if texto_mensagem.startswith('!'):
                            pergunta = texto_mensagem[1:].strip()
                        
                        # Obter resposta do assistente
                        logger.info(f"🤔 Enviando pergunta para o assistente: {pergunta}")
                        resposta = self.obter_resposta_assistente(pergunta)
                        
                        # Extrair um nome de usuário mais curto
                        nome_curto = self.extrair_nome_usuario(nome_autor)
                        
                        # Formatar e enviar resposta
                        resposta_formatada = f"@{nome_curto} {resposta}"
                        resposta_enviada = self.enviar_mensagem_chat(resposta_formatada)
                        
                        if resposta_enviada:
                            self.id_ultima_mensagem_bot = resposta_enviada.get('id')
                            logger.info(f"🤖 Resposta enviada: {resposta_formatada}")
                            self.stats["messages_responded"] += 1
                
                # Limitar o tamanho do conjunto para evitar uso excessivo de memória
                if len(self.mensagens_processadas) > MAX_MESSAGES_MEMORY:
                    # Manter apenas as mensagens mais recentes
                    self.mensagens_processadas = set(list(self.mensagens_processadas)[-MAX_MESSAGES_MEMORY:])
                
        except KeyboardInterrupt:
            logger.info("\n🛑 Monitoramento interrompido pelo usuário")
        except Exception as e:
            logger.error(f"Erro ao monitorar chat: {e}")
            self.stats["errors"] += 1
        finally:
            self.stats["end_time"] = datetime.now()
            self.bot_running = False
            self._mostrar_estatisticas()
    
    def _mostrar_estatisticas(self):
        """Mostra estatísticas da sessão do bot."""
        if self.stats["start_time"] and self.stats["end_time"]:
            duracao = self.stats["end_time"] - self.stats["start_time"]
            duracao_minutos = duracao.total_seconds() / 60
            
            logger.info("\n===== ESTATÍSTICAS DA SESSÃO =====")
            logger.info(f"Duração: {duracao_minutos:.1f} minutos")
            logger.info(f"Mensagens recebidas: {self.stats['messages_received']}")
            logger.info(f"Respostas enviadas: {self.stats['messages_responded']}")
            logger.info(f"Chamadas de API: {self.stats['api_calls']}")
            logger.info(f"Erros: {self.stats['errors']}")
            logger.info(f"Uso de cota estimado: {self.quota_usage} unidades")
            logger.info("==================================\n")
    
    def run(self, args=None):
        """Executa o bot com as configurações especificadas."""
        # Parse argumentos se não fornecidos
        if args is None:
            parser = argparse.ArgumentParser(description=f'Janete YouTube Bot v{VERSION}')
            parser.add_argument('-t', '--transmissao', help='ID da transmissão do YouTube')
            parser.add_argument('-i', '--intervalo', type=int, help='Intervalo entre verificações (segundos)')
            parser.add_argument('-e', '--economia', action='store_true', help='Ativar modo de economia de cota')
            args = parser.parse_args()
        
        logger.info(f"Iniciando Janete YouTube Bot v{VERSION}")
        
        # Configurar com argumentos da linha de comando
        if not self.setup(args):
            return
        
        # Autenticar nas APIs
        if not self.autenticar_youtube() or not self.autenticar_openai():
            return
        
        # Obter ID do chat ao vivo
        if not self.obter_live_chat_id():
            return
        
        # Iniciar monitoramento
        self.monitorar_chat()

if __name__ == "__main__":
    bot = JaneteBot()
    bot.run()
