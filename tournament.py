import threading
import tkinter as tk
from tkinter import ttk
import chess
import chess.engine
import os
import concurrent.futures
import random

class TournamentRunner:
    def __init__(self, root, config1, config2, num_games=100, concurrent_games=12):
        self.root = root
        self.config1 = config1
        self.config2 = config2
        self.num_games = num_games
        self.concurrent_games = concurrent_games

        self.starting_fens = []
        epd_path = "chess.epd"

        if os.path.exists(epd_path):
            with open(epd_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.starting_fens.append(line)

        if not self.starting_fens:
            raise FileNotFoundError()
        
        self.e1_name = os.path.basename(config1['path']).split('.')[0]
        self.e2_name = os.path.basename(config2['path']).split('.')[0]
        
        self.e1_wins = 0
        self.e2_wins = 0
        self.draws = 0
        
        self.e1_depths = []
        self.e2_depths = []
        
        self.e1_npms = []
        self.e2_npms = []
        
        self.games_completed = 0
        self.is_running = True

        self.setup_ui()
        
        self.thread = threading.Thread(target=self.run_tournament, daemon=True)
        self.thread.start()

    def get_starting_board(self, game_id):
        pair_id = (game_id - 1) // 2
        rng = random.Random(pair_id)
        fen_index = rng.randint(0, len(self.starting_fens) - 1)
        
        epd_string = self.starting_fens[fen_index]
        
        board = chess.Board()
        if epd_string != chess.STARTING_FEN:
            board.set_epd(epd_string) 
            
        return board

    def setup_ui(self):
        self.window = tk.Toplevel(self.root)
        self.window.title(f"Tournament: {self.e1_name} vs {self.e2_name}")
        self.window.geometry("450x320")
        
        self.window.protocol("WM_DELETE_WINDOW", self.close_window_handler)

        self.progress_lbl = ttk.Label(self.window, text="Starting...", font=("Arial", 12, "bold"))
        self.progress_lbl.pack(pady=10)

        self.score_lbl = ttk.Label(self.window, text=f"{self.e1_name}: 0 | {self.e2_name}: 0 | Draws: 0", font=("Arial", 11))
        self.score_lbl.pack(pady=5)

        self.e1_depth_lbl = ttk.Label(self.window, text=f"{self.e1_name} Avg Depth: -", font=("Arial", 10))
        self.e1_depth_lbl.pack(pady=2)
        self.e2_depth_lbl = ttk.Label(self.window, text=f"{self.e2_name} Avg Depth: -", font=("Arial", 10))
        self.e2_depth_lbl.pack(pady=2)

        self.e1_npms_lbl = ttk.Label(self.window, text=f"{self.e1_name} Avg nodes per ms: -", font=("Arial", 10))
        self.e1_npms_lbl.pack(pady=2)
        self.e2_npms_lbl = ttk.Label(self.window, text=f"{self.e2_name} Avg nodes per ms: -", font=("Arial", 10))
        self.e2_npms_lbl.pack(pady=2)

        self.stop_btn = ttk.Button(self.window, text="Stop Tournament", command=self.stop_tournament)
        self.stop_btn.pack(pady=15)

        self.copy_btn = ttk.Button(self.window, text="Copy result to clipboard", command=self.copy_to_clipboard)
        self.copy_btn.pack(pady=5)

    def update_ui(self):
        if not tk.Toplevel.winfo_exists(self.window):
            return
            
        self.progress_lbl.config(text=f"Completed {self.games_completed} of {self.num_games}")
        self.score_lbl.config(
            text=f"{self.e1_name} Wins: {self.e1_wins} | {self.e2_name} Wins: {self.e2_wins} | Draws: {self.draws}"
        )
        
        if self.e1_depths:
            avg_1_depth = self.get_trimmed_average(self.e1_depths, 0.05)
            self.e1_depth_lbl.config(text=f"{self.e1_name} Avg Depth: {avg_1_depth:.1f}")
            
        if self.e2_depths:
            avg_2_depth = self.get_trimmed_average(self.e2_depths, 0.05)
            self.e2_depth_lbl.config(text=f"{self.e2_name} Avg Depth: {avg_2_depth:.1f}")

        if self.e1_npms:
            avg_1_npms = self.get_trimmed_average(self.e1_npms, 0.05)
            self.e1_npms_lbl.config(text=f"{self.e1_name} Avg NPMS: {avg_1_npms:.0f}")
            
        if self.e2_npms:
            avg_2_npms = self.get_trimmed_average(self.e2_npms, 0.05)
            self.e2_npms_lbl.config(text=f"{self.e2_name} Avg NPMS: {avg_2_npms:.0f}")

    def get_trimmed_average(self, data_list, trim_percent=0.05):
        n = len(data_list)
        if n == 0: return 0
        trim_count = int(n * trim_percent)
        if trim_count == 0: return sum(data_list) / n
        sorted_data = sorted(data_list)
        trimmed_data = sorted_data[trim_count : -trim_count]
        return sum(trimmed_data) / len(trimmed_data)

    def stop_tournament(self):
        if not self.is_running:
            return
            
        self.is_running = False
        try:
            if self.window.winfo_exists():
                self.progress_lbl.config(text="Stopping... (finishing current moves)")
                self.stop_btn.config(state=tk.DISABLED)
        except Exception:
            pass
    
    def finalize_ui(self):
        try:
            if not self.window.winfo_exists():
                return
                
            if self.is_running:
                self.progress_lbl.config(text="Tournament Complete!")
            else:
                self.progress_lbl.config(text="Tournament Stopped. Final Stats:")
                
            self.stop_btn.config(text="Close Window", command=self.window.destroy, state=tk.NORMAL)
        except Exception:
            pass

    def close_window_handler(self):
        self.stop_tournament()
        self.window.destroy()
    
    def play_single_game(self, game_id):
        if not self.is_running:
            return None

        engine1 = None
        engine2 = None
        engine1_is_white = (game_id % 2 != 0)
        
        result_data = {
            "result": None,
            "e1_depths": [],
            "e2_depths": [],
            "e1_npms": [],
            "e2_npms": [],
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

            if not hasattr(self, 'active_engines'):
                self.active_engines = {}
            self.active_engines[game_id] = (engine1, engine2)

            board = self.get_starting_board(game_id)
            
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
                
                move_result = active_engine.play(
                    board, 
                    chess.engine.Limit(depth=active_config['depth'], time=time_limit), 
                    info=chess.engine.INFO_ALL
                )
                
                info = move_result.info
                actual_depth = info.get("depth", active_config['depth'])
                npms = None
                
                if "nps" in info and info["nps"] is not None:
                    npms = info["nps"] / 1000.0 
                elif "nodes" in info and "time" in info and info["time"] > 0:
                    npms = info["nodes"] / info["time"]

                if active_engine == engine1:
                    if actual_depth is not None: result_data["e1_depths"].append(actual_depth)
                    if npms is not None: result_data["e1_npms"].append(npms)
                else:
                    if actual_depth is not None: result_data["e2_depths"].append(actual_depth)
                    if npms is not None: result_data["e2_npms"].append(npms)
                
                board.push(move_result.move)

            if not self.is_running:
                result_data["result"] = "STOPPED"
            else:
                result_data["result"] = board.result()

        except Exception as e:
            if self.is_running:
                print(f"\n--- CRASH DETECTED IN GAME {game_id} ---")
                print(f"Error: {e}")
                print("-" * 40 + "\n")
                result_data["result"] = "CRASH"
            else:
                result_data["result"] = "STOPPED"
        finally:
            if engine1:
                try: engine1.quit()
                except: pass
            if engine2:
                try: engine2.quit()
                except: pass
            if hasattr(self, 'active_engines') and game_id in self.active_engines:
                try: del self.active_engines[game_id]
                except: pass

        return result_data

    def copy_to_clipboard(self):
        self.window.clipboard_clear()
        
        avg_1_depth = self.get_trimmed_average(self.e1_depths, 0.05) if self.e1_depths else 0
        avg_2_depth = self.get_trimmed_average(self.e2_depths, 0.05) if self.e2_depths else 0
        
        avg_1_npms = self.get_trimmed_average(self.e1_npms, 0.05) if self.e1_npms else 0
        avg_2_npms = self.get_trimmed_average(self.e2_npms, 0.05) if self.e2_npms else 0

        result_text = (
            f"{self.games_completed} game tournament.\n"
            f"Engine {self.e1_name} config: {self.config1.get('time', 0)} ms per move; {self.config1.get('threads', 1)} threads\n"
            f"Engine {self.e2_name} config: {self.config2.get('time', 0)} ms per move; {self.config2.get('threads', 1)} threads\n"
            f"{self.e1_name} wins/{self.e2_name} wins/draws: {self.e1_wins}/{self.e2_wins}/{self.draws}\n"
            f"Avg depth: {self.e1_name}: {avg_1_depth:.1f}; {self.e2_name}: {avg_2_depth:.1f}\n"
            f"Avg nodes per ms: {self.e1_name} : {avg_1_npms:.0f}; {self.e2_name}: {avg_2_npms:.0f}"
        )
        
        self.window.clipboard_append(result_text)
        self.window.update()

    def run_tournament(self):
        game_ids = list(range(1, self.num_games + 1))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrent_games) as executor:
            futures = [executor.submit(self.play_single_game, gid) for gid in game_ids]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    data = future.result()
                except:
                    continue

                if not data or data["result"] in ("CRASH", "STOPPED", None):
                    continue 

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
                self.e1_npms.extend(data["e1_npms"])
                self.e2_npms.extend(data["e2_npms"])
                self.games_completed += 1
                
                self.root.after(0, self.update_ui)

        self.root.after(0, self.finalize_ui)