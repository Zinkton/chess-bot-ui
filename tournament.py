import threading
import tkinter as tk
from tkinter import ttk
import chess
import chess.engine
import os

class TournamentRunner:
    def __init__(self, root, engine1_exe, engine2_exe, num_games=100, depth=100):
        self.root = root
        self.engine1_exe = engine1_exe
        self.engine2_exe = engine2_exe
        self.num_games = num_games
        self.depth_limit = depth
        
        # Get clean names for the UI (e.g., "stockfish_15" instead of the full path)
        self.e1_name = os.path.basename(engine1_exe).split('.')[0]
        self.e2_name = os.path.basename(engine2_exe).split('.')[0]
        
        # Stats tracking per engine
        self.e1_wins = 0
        self.e2_wins = 0
        self.draws = 0
        
        self.e1_depths = []
        self.e2_depths = []
        
        self.current_game = 0
        self.is_running = True

        self.setup_ui()
        
        self.thread = threading.Thread(target=self.run_tournament, daemon=True)
        self.thread.start()

    def setup_ui(self):
        self.window = tk.Toplevel(self.root)
        self.window.title(f"Tournament: {self.e1_name} vs {self.e2_name}")
        self.window.geometry("450x250")
        self.window.protocol("WM_DELETE_WINDOW", self.stop_tournament)

        self.progress_lbl = ttk.Label(self.window, text="Starting...", font=("Arial", 12, "bold"))
        self.progress_lbl.pack(pady=10)

        self.score_lbl = ttk.Label(self.window, text=f"{self.e1_name}: 0 | {self.e2_name}: 0 | Draws: 0", font=("Arial", 11))
        self.score_lbl.pack(pady=5)

        self.e1_depth_lbl = ttk.Label(self.window, text=f"{self.e1_name} Avg Depth: -", font=("Arial", 10))
        self.e1_depth_lbl.pack(pady=2)

        self.e2_depth_lbl = ttk.Label(self.window, text=f"{self.e2_name} Avg Depth: -", font=("Arial", 10))
        self.e2_depth_lbl.pack(pady=2)

        self.stop_btn = ttk.Button(self.window, text="Stop Tournament", command=self.stop_tournament)
        self.stop_btn.pack(pady=15)

    def update_ui(self):
        self.progress_lbl.config(text=f"Game {self.current_game} of {self.num_games}")
        self.score_lbl.config(
            text=f"{self.e1_name} Wins: {self.e1_wins} | {self.e2_name} Wins: {self.e2_wins} | Draws: {self.draws}"
        )
        
        if self.e1_depths:
            avg_1 = sum(self.e1_depths) / len(self.e1_depths)
            self.e1_depth_lbl.config(text=f"{self.e1_name} Avg Depth: {avg_1:.1f}")
            
        if self.e2_depths:
            avg_2 = sum(self.e2_depths) / len(self.e2_depths)
            self.e2_depth_lbl.config(text=f"{self.e2_name} Avg Depth: {avg_2:.1f}")

    def stop_tournament(self):
        self.is_running = False
        self.progress_lbl.config(text="Tournament Stopped.")
        self.stop_btn.config(text="Close", command=self.window.destroy)

    def run_tournament(self):
        engine1 = None
        engine2 = None

        def start_engines():
            """Helper function to boot/reboot engines and safely apply limits."""
            nonlocal engine1, engine2
            # Clean up old instances if they exist
            if engine1:
                try: engine1.quit()
                except: pass
            if engine2:
                try: engine2.quit()
                except: pass
            
            # Start fresh instances
            engine1 = chess.engine.SimpleEngine.popen_uci(self.engine1_exe)
            engine2 = chess.engine.SimpleEngine.popen_uci(self.engine2_exe)

        try:
            start_engines()
            
            i = 1
            while i <= self.num_games and self.is_running:
                self.current_game = i
                board = chess.Board()
                engine1_is_white = (i % 2 != 0)
                game_crashed = False
                
                try:
                    while not board.is_game_over() and self.is_running:
                        is_white_turn = board.turn == chess.WHITE
                        
                        if engine1_is_white:
                            active_engine = engine1 if is_white_turn else engine2
                        else:
                            active_engine = engine2 if is_white_turn else engine1
                        
                        result = active_engine.play(
                            board, 
                            chess.engine.Limit(depth=self.depth_limit), 
                            info=chess.engine.INFO_ALL
                        )
                        
                        actual_depth = result.info.get("depth", self.depth_limit)
                        if active_engine == engine1:
                            self.e1_depths.append(actual_depth)
                        else:
                            self.e2_depths.append(actual_depth)
                            
                        board.push(result.move)

                except Exception as game_err:
                    print(f"\n--- CRASH DETECTED IN GAME {i} ---")
                    print(f"Error: {game_err}")
                    print("Game history before crash:")
                    # This prints standard chess notation (e.g., 1. e4 e5 2. Nf3)
                    print(chess.Board().variation_san(board.move_stack))
                    print("\nRestarting engines and retrying this game...\n")
                    
                    start_engines()
                    game_crashed = True # Mark so we don't score this game

                # Only score and advance to the next game if it finished without crashing
                if not game_crashed and self.is_running:
                    game_result = board.result()
                    
                    if game_result == "1/2-1/2":
                        self.draws += 1
                    elif game_result == "1-0":
                        if engine1_is_white: self.e1_wins += 1
                        else: self.e2_wins += 1
                    elif game_result == "0-1":
                        if engine1_is_white: self.e2_wins += 1
                        else: self.e1_wins += 1
                    
                    self.root.after(0, self.update_ui)
                    i += 1 # Advance to the next game

            if self.is_running:
                self.root.after(0, lambda: self.progress_lbl.config(text="Tournament Complete!"))
                self.root.after(0, lambda: self.stop_btn.config(text="Close", command=self.window.destroy))

        except Exception as e:
            print(f"Tournament fatal error: {e}")
        finally:
            # Ensure engines are closed when the thread finishes
            if engine1:
                try: engine1.quit()
                except: pass
            if engine2:
                try: engine2.quit()
                except: pass