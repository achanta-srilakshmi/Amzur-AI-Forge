import { useEffect, useMemo, useRef, useState } from "react";

import { api, ApiError } from "../../lib/api";

type Cell = "" | "X" | "O";
type Winner = "X" | "O" | "draw" | null;

type HistoryItem = {
  player: "X" | "O";
  cell: number;
  message: string;
};

type MoveResponse = {
  board: Cell[];
  ai_cell: number | null;
  ai_message: string;
  winner: Winner;
  history: HistoryItem[];
};

const LINES: Array<[number, number, number]> = [
  [0, 1, 2],
  [3, 4, 5],
  [6, 7, 8],
  [0, 3, 6],
  [1, 4, 7],
  [2, 5, 8],
  [0, 4, 8],
  [2, 4, 6],
];

function findWinningCells(board: Cell[], winner: Winner): number[] {
  if (winner !== "X" && winner !== "O") {
    return [];
  }

  for (const [a, b, c] of LINES) {
    if (board[a] === winner && board[b] === winner && board[c] === winner) {
      return [a, b, c];
    }
  }

  return [];
}

function resultLabel(winner: Winner): string | null {
  if (winner === "X") return "You win!";
  if (winner === "O") return "I win!";
  if (winner === "draw") return "It's a draw!";
  return null;
}

function toApiHistory(history: HistoryItem[]): HistoryItem[] {
  return history
    .filter((entry) => (entry.player === "X" || entry.player === "O") && entry.cell >= 1 && entry.cell <= 9)
    .map((entry) => ({ player: entry.player, cell: entry.cell, message: entry.message }));
}

export function TicTacToePanel() {
  const [board, setBoard] = useState<Cell[]>(Array(9).fill("") as Cell[]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [winner, setWinner] = useState<Winner>(null);
  const [aiThinking, setAiThinking] = useState(false);
  const [streamingAi, setStreamingAi] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [score, setScore] = useState({ x: 0, o: 0, draw: 0 });

  const bottomRef = useRef<HTMLDivElement>(null);
  const lastScoredWinner = useRef<Winner>(null);
  const choosingBubbleRef = useRef(false);

  const winCells = useMemo(() => findWinningCells(board, winner), [board, winner]);
  const result = resultLabel(winner);
  const boardDisabled = aiThinking || streamingAi || winner !== null;
  const leader =
    score.x === score.o ? "Tied" : score.x > score.o ? "You are ahead" : "AI is ahead";
  const roundStatus = winner
    ? result
    : aiThinking || streamingAi
      ? "AI is choosing a move..."
      : history.length > 0
        ? "Your turn"
        : "Start the round";

  useEffect(() => {
    if (!winner || lastScoredWinner.current === winner) {
      return;
    }

    setScore((prev) => {
      if (winner === "X") return { ...prev, x: prev.x + 1 };
      if (winner === "O") return { ...prev, o: prev.o + 1 };
      return { ...prev, draw: prev.draw + 1 };
    });

    lastScoredWinner.current = winner;
  }, [winner]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, aiThinking, error, result]);

  const streamAiBubble = async (cell: number, text: string): Promise<void> => {
    setStreamingAi(true);

    setHistory((prev) => [...prev, { player: "O", cell, message: "" }]);

    for (let i = 1; i <= text.length; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 16));
      const partial = text.slice(0, i);
      setHistory((prev) => {
        if (prev.length === 0) return prev;
        const next = [...prev];
        const last = next[next.length - 1];
        if (!last || last.player !== "O" || last.cell !== cell) {
          return prev;
        }
        next[next.length - 1] = { ...last, message: partial };
        return next;
      });
    }

    setStreamingAi(false);
  };

  const playCell = async (index: number) => {
    if (boardDisabled || board[index] !== "") {
      return;
    }

    setError(null);

    const userCell = index + 1;
    const nextBoard = [...board] as Cell[];
    nextBoard[index] = "X";

    const userEntry: HistoryItem = {
      player: "X",
      cell: userCell,
      message: `I played cell ${userCell}`,
    };

    const requestHistoryForUi = [...history, userEntry];
    const requestHistoryForApi = toApiHistory(requestHistoryForUi);
    const choosingEntry: HistoryItem = {
      player: "O",
      cell: 0,
      message: "AI is choosing a move...",
    };

    setBoard(nextBoard);
    setHistory([...requestHistoryForUi, choosingEntry]);
    choosingBubbleRef.current = true;
    setAiThinking(true);

    try {
      const response = await api.post<MoveResponse>("/tictactoe/move", {
        board: nextBoard,
        history: requestHistoryForApi,
        user_move: userCell,
      });

      setBoard(response.board);
      setWinner(response.winner);

      const aiCell = response.ai_cell;
      const aiMessage = response.ai_message?.trim() || "I made my move.";

      setHistory((prev) => {
        const next = [...prev];
        if (choosingBubbleRef.current && next.length > 0) {
          next.pop();
        }
        if (aiCell !== null) {
          next.push({ player: "O", cell: aiCell, message: `AI chose cell ${aiCell}` });
        } else {
          next.push({ player: "O", cell: 0, message: aiMessage });
        }
        choosingBubbleRef.current = false;
        return next;
      });

      if (aiCell !== null) {
        await streamAiBubble(aiCell, aiMessage);
      }
    } catch (err) {
      if (choosingBubbleRef.current) {
        setHistory((prev) =>
          prev.filter((entry) => !(entry.cell === 0 && entry.message === "AI is choosing a move..."))
        );
        choosingBubbleRef.current = false;
      }
      if (err instanceof ApiError) {
        const detail = err.detail as { message?: string } | undefined;
        setError(detail?.message ?? "Unable to complete AI move.");
      } else {
        setError("Unable to complete AI move.");
      }
    } finally {
      setAiThinking(false);
    }
  };

  const resetGame = () => {
    setBoard(Array(9).fill("") as Cell[]);
    setHistory([]);
    setWinner(null);
    setAiThinking(false);
    setStreamingAi(false);
    setError(null);
    lastScoredWinner.current = null;
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-linear-to-br from-white via-slate-50 to-rose-50/40 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950">
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
        <div className="mb-4 rounded-3xl border border-rose-100 bg-white/90 p-4 shadow-[0_14px_40px_rgba(15,23,42,0.08)] backdrop-blur dark:border-slate-700 dark:bg-slate-900/80">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="inline-flex items-center rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-rose-600 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300">
                AI Duel
              </div>
              <h3 className="mt-2 text-xl font-black tracking-tight text-slate-900 dark:text-white">
                Tic Tac Toe Arena
              </h3>
              <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-600 dark:text-slate-300">
                You play as <span className="font-semibold text-blue-600 dark:text-blue-400">X</span>.
                The agent plays as <span className="font-semibold text-rose-600 dark:text-rose-400">O</span>.
                First to three in a row wins the round, and the scoreboard keeps the match history.
              </p>
            </div>

            <button
              type="button"
              onClick={resetGame}
              className="inline-flex items-center justify-center rounded-xl bg-linear-to-r from-rose-500 to-orange-500 px-3 py-2 text-xs font-semibold text-white shadow-lg shadow-rose-500/20 transition hover:scale-[1.01] hover:from-rose-400 hover:to-orange-400"
            >
              Play Again
            </button>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <div className="inline-flex items-center gap-2 rounded-xl border border-blue-100 bg-blue-50/80 px-3 py-1.5 text-xs font-semibold text-blue-700 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-300">
              <span>You</span>
              <span className="text-base font-black">{score.x}</span>
            </div>
            <div className="inline-flex items-center gap-2 rounded-xl border border-rose-100 bg-rose-50/80 px-3 py-1.5 text-xs font-semibold text-rose-700 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-300">
              <span>AI</span>
              <span className="text-base font-black">{score.o}</span>
            </div>
            <div className="inline-flex items-center gap-2 rounded-xl border border-emerald-100 bg-emerald-50/80 px-3 py-1.5 text-xs font-semibold text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300">
              <span>Draws</span>
              <span className="text-base font-black">{score.draw}</span>
            </div>
            <div className="inline-flex items-center rounded-xl border border-slate-200 bg-white/80 px-3 py-1.5 text-xs font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-300">
              Leader: <span className="ml-1 text-slate-900 dark:text-white">{leader}</span>
            </div>
          </div>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-hidden lg:grid-cols-[minmax(320px,420px)_minmax(0,1fr)]">
          <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-[0_12px_36px_rgba(15,23,42,0.08)] dark:border-slate-700 dark:bg-slate-900/70">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h4 className="text-base font-semibold text-slate-800 dark:text-slate-100">Match Board</h4>
                <p className="text-xs text-slate-500 dark:text-slate-400">Tap a square to make your move.</p>
              </div>
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                winner === "X"
                  ? "bg-blue-100 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300"
                  : winner === "O"
                    ? "bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300"
                    : winner === "draw"
                      ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300"
                      : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
              }`}>
                {winner === null ? "Round live" : result}
              </span>
            </div>

            <div className="mb-4 flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                {roundStatus}
              </span>
              <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-300">
                You play X
              </span>
              <span className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300">
                AI plays O
              </span>
            </div>

            {result && (
              <div className={`mb-4 rounded-2xl border px-4 py-3 text-sm font-semibold shadow-sm ${
                winner === "X"
                  ? "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-300"
                  : winner === "O"
                    ? "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-300"
                    : "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300"
              }`}>
                {result}
              </div>
            )}

            <div className="mx-auto w-full max-w-90">
              <div className="grid grid-cols-3 gap-2.5">
              {board.map((value, idx) => {
                const isWinCell = winCells.includes(idx);
                return (
                  <button
                    key={`cell-${idx}`}
                    type="button"
                    onClick={() => {
                      void playCell(idx);
                    }}
                    disabled={boardDisabled || value !== ""}
                    className={`group aspect-square rounded-2xl border text-3xl font-black transition duration-200 ${
                      isWinCell
                        ? "border-emerald-500 bg-emerald-100 shadow-[0_0_0_4px_rgba(16,185,129,0.12)] dark:bg-emerald-900/30"
                          : "border-slate-200 bg-linear-to-br from-white to-slate-50 hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-lg dark:border-slate-700 dark:from-slate-900 dark:to-slate-800 dark:hover:border-slate-500"
                    } ${boardDisabled || value !== "" ? "cursor-not-allowed opacity-90" : "cursor-pointer"}`}
                    aria-label={`Cell ${idx + 1}`}
                  >
                    {value === "X" && <span className="text-blue-600 drop-shadow-sm dark:text-blue-400">X</span>}
                    {value === "O" && <span className="text-rose-600 drop-shadow-sm dark:text-rose-400">O</span>}
                  </button>
                );
              })}
              </div>
            </div>
          </section>

          <section className="flex min-h-0 flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_12px_36px_rgba(15,23,42,0.08)] dark:border-slate-700 dark:bg-slate-900/60">
            <div className="border-b border-slate-200 px-4 py-3 dark:border-slate-700">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Match Commentary</h4>
                  <p className="text-xs text-slate-500 dark:text-slate-400">Moves, taunts, and the final verdict.</p>
                </div>
                <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                  {winner === null ? "In progress" : "Round finished"}
                </div>
              </div>
            </div>

            <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
              {history.length === 0 && !aiThinking && (
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-400">
                  The scoreboard is ready. Start with a strong opening move.
                </div>
              )}

              {history.map((entry, idx) => (
                <div
                  key={`${entry.player}-${entry.cell}-${idx}`}
                  className={`flex ${entry.player === "X" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-3xl px-4 py-3 text-sm shadow-sm ${
                      entry.player === "X"
                        ? "rounded-tr-md bg-linear-to-br from-blue-600 to-indigo-600 text-white"
                        : "rounded-tl-md border border-slate-200 bg-slate-100 text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                    }`}
                  >
                    <div className="mb-1 text-[11px] font-bold uppercase tracking-[0.14em] opacity-80">
                      {entry.player === "X" ? "You" : "AI"}
                    </div>
                    {entry.message}
                  </div>
                </div>
              ))}

              {aiThinking && (
                <div className="flex justify-start">
                  <div className="rounded-3xl rounded-tl-md border border-slate-200 bg-slate-100 px-4 py-3 text-sm text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
                    AI is thinking...
                  </div>
                </div>
              )}

              {error && (
                <div className="rounded-3xl border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-700 shadow-sm dark:border-rose-700 dark:bg-rose-900/20 dark:text-rose-300">
                  {error}
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
