import threading
import tkinter as tk
from tkinter import ttk
import chess
import chess.engine
import os
import concurrent.futures

class TournamentRunner:
    def __init__(self, root, config1, config2, num_games=100):
        self.root = root
        self.config1 = config1
        self.config2 = config2
        self.num_games = num_games
        
        self.e1_name = os.path.basename(config1['path']).split('.')[0]
        self.e2_name = os.path.basename(config2['path']).split('.')[0]
        
        # Stats tracking per engine
        self.e1_wins = 0
        self.e2_wins = 0
        self.draws = 0
        
        self.e1_depths = []
        self.e2_depths = []
        
        self.games_completed = 0
        self.is_running = True

        self.concurrent_games = 12

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
        self.progress_lbl.config(text=f"Completed {self.games_completed} of {self.num_games}")
        self.score_lbl.config(
            text=f"{self.e1_name} Wins: {self.e1_wins} | {self.e2_name} Wins: {self.e2_wins} | Draws: {self.draws}"
        )
        
        if self.e1_depths:
            avg_1 = self.get_trimmed_average(self.e1_depths, 0.05)
            self.e1_depth_lbl.config(text=f"{self.e1_name} Avg Depth: {avg_1:.1f}")
            
        if self.e2_depths:
            avg_2 = self.get_trimmed_average(self.e2_depths, 0.05)
            self.e2_depth_lbl.config(text=f"{self.e2_name} Avg Depth: {avg_2:.1f}")

    def get_trimmed_average(self, depths, trim_percent=0.05):
        n = len(depths)
        if n == 0: return 0
        trim_count = int(n * trim_percent)
        if trim_count == 0: return sum(depths) / n
        sorted_depths = sorted(depths)
        trimmed_depths = sorted_depths[trim_count : -trim_count]
        return sum(trimmed_depths) / len(trimmed_depths)

    def stop_tournament(self):
        self.is_running = False
        self.progress_lbl.config(text="Stopping... (Waiting for active games)")
        self.stop_btn.config(state=tk.DISABLED)
    
    def play_single_game(self, game_id):
        """Runs a completely isolated game with its own engine processes."""
        if not self.is_running:
            return None

        engine1 = None
        engine2 = None
        engine1_is_white = (game_id % 2 != 0)
        
        result_data = {
            "result": None,
            "e1_depths": [],
            "e2_depths": [],
            "e1_is_white": engine1_is_white
        }

        try:
            engine1 = chess.engine.SimpleEngine.popen_uci(self.config1['path'])
            engine2 = chess.engine.SimpleEngine.popen_uci(self.config2['path'])

            if self.config1['threads']:
                try: engine1.configure({"Threads": self.config1['threads']})
                except: pass
            if self.config2['threads']:
                try: engine2.configure({"Threads": self.config2['threads']})
                except: pass

            board = chess.Board()
            
            while not board.is_game_over() and self.is_running:
                is_white_turn = board.turn == chess.WHITE
                
                if engine1_is_white:
                    active_engine = engine1 if is_white_turn else engine2
                    active_config = self.config1 if is_white_turn else self.config2
                else:
                    active_engine = engine2 if is_white_turn else engine1
                    active_config = self.config2 if is_white_turn else self.config1
                
                time_limit = (active_config['time'] / 1000.0) if active_config['time'] else None
                
                move_result = active_engine.play(
                    board, 
                    chess.engine.Limit(depth=active_config['depth'], time=time_limit), 
                    info=chess.engine.INFO_ALL
                )
                
                actual_depth = move_result.info.get("depth", active_config['depth'])
                if actual_depth is not None:
                    if active_engine == engine1:
                        result_data["e1_depths"].append(actual_depth)
                    else:
                        result_data["e2_depths"].append(actual_depth)
                
                board.push(move_result.move)

            result_data["result"] = board.result()

        except Exception as e:
            print(f"\n--- CRASH DETECTED IN GAME {game_id} ---")
            print(f"Error: {e}")
            print("Game history before crash:")
            try:
                print(chess.Board().variation_san(board.move_stack))
            except Exception:
                # Fallback to UCI strings if the SAN conversion itself fails
                print([move.uci() for move in board.move_stack])
            print("-" * 40 + "\n")
            result_data["result"] = "CRASH"
        finally:
            if engine1:
                try: engine1.quit()
                except: pass
            if engine2:
                try: engine2.quit()
                except: pass

        return result_data

    def run_tournament(self):
        game_ids = list(range(1, self.num_games + 1))
        
        # Run games in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrent_games) as executor:
            futures = [executor.submit(self.play_single_game, gid) for gid in game_ids]
            
            for future in concurrent.futures.as_completed(futures):
                if not self.is_running:
                    break
                    
                data = future.result()
                if not data or data["result"] == "CRASH":
                    continue # You could implement retry logic here

                # Tally scores safely in the main thread space
                game_result = data["result"]
                engine1_is_white = data["e1_is_white"]

                if game_result == "1/2-1/2":
                    self.draws += 1
                elif game_result == "1-0":
                    if engine1_is_white: self.e1_wins += 1
                    else: self.e2_wins += 1
                elif game_result == "0-1":
                    if engine1_is_white: self.e2_wins += 1
                    else: self.e1_wins += 1

                self.e1_depths.extend(data["e1_depths"])
                self.e2_depths.extend(data["e2_depths"])
                self.games_completed += 1
                
                # Push GUI updates to Tkinter's main thread
                self.root.after(0, self.update_ui)

        self.root.after(0, lambda: self.progress_lbl.config(text="Tournament Complete!"))
        self.root.after(0, lambda: self.stop_btn.config(text="Close", command=self.window.destroy, state=tk.NORMAL))