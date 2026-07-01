TOOL_DECLARATIONS = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Abre qualquer aplicativo instalado no sistema.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Nome do app. Ex: 'chrome', 'spotify', 'vscode'.",
                    }
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "computer_control",
            "description": "Controla o PC no Windows: minimizar janelas, screenshot, bloquear tela, volume, mute.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Acao: 'fechar', 'minimizar_tudo', 'print', 'bloqueio', 'volume', 'mute'.",
                    },
                    "nivel": {
                        "type": "integer",
                        "description": "Volume 0-100 (só para action='volume').",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cmd_control",
            "description": "Executa comandos de terminal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Descrição da tarefa em português.",
                    },
                },
                "required": ["task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Pesquisa na web e retorna resumo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Termo de pesquisa."}
                },
                "required": ["query"],
            },
        },
    },
]
