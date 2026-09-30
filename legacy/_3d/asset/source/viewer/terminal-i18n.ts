export type TerminalMessages = {
    connecting: string;
    connected: string;
    reconnecting: string;
    error: string;
    unavailable: string;
    instruction: string;
    output: string;
    commandFailed: string;
    exitCode: string;
    command: string;
    missingId: string;
    missingPoint: string;
};

export class TerminalI18n {
    // English is the default catalog for languages not supported by this viewer.
    static messages(language: string): TerminalMessages {
        const locale: string = language.toLowerCase().replace(/_/g, "-");
        if (locale === "pt" || locale.startsWith("pt-")) {
            return {
                connecting: "Conectando…",
                connected: "Conectado",
                reconnecting: "Reconectando…",
                error: "ERRO DE CONEXÃO",
                unavailable: "O servidor local não está disponível ou a conexão SSE foi interrompida.",
                instruction: "Para iniciar o servidor, execute no terminal do PC:",
                output: "Saída do terminal",
                commandFailed: "Falha ao enviar comando",
                exitCode: "Código de saída",
                command: "Comando do terminal",
                missingId: "O nó selecionado não possui um GlobalId válido.",
                missingPoint: "O duplo clique não atingiu ponto algum do modelo.",
            };
        }
        return {
            connecting: "Connecting…",
            connected: "Connected",
            reconnecting: "Reconnecting…",
            error: "CONNECTION ERROR",
            unavailable: "The local server is unavailable or the SSE connection was interrupted.",
            instruction: "To start the server, run in your PC terminal:",
            output: "Terminal output",
            commandFailed: "Could not send command",
            exitCode: "Exit code",
            command: "Terminal command",
            missingId: "The selected node does not have a valid GlobalId.",
            missingPoint: "The double click did not land on any point of the model.",
        };
    }
}
