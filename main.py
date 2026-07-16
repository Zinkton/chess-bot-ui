import threading
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
import chess
import chess.engine
import time

from chess_model import ChessModel
from chess_view import ChessView
from tournament import TournamentRunner

class ChessController:
    def __init__(self, root):
        self.model = ChessModel()
        self.view = ChessView(root, self)
        
        self.selected_square = None
        self.dragging = False
        self.drag_start_square = None
        
        self.current_position_index = -1
        self.viewing_history = False
        self.display_board = self.model.board
        
        self.engine_white = None
        self.engine_black = None
        
        self.config_white = None
        self.config_black = None

        self.view.root.after(50, self.ask_game_mode)
        
    def _close_engines(self):
        """Safely terminates active engines."""
        if getattr(self, 'engine_white', None):
            try: self.engine_white.quit()
            except: pass
            self.engine_white = None
        if getattr(self, 'engine_black', None):
            try: self.engine_black.quit()
            except: pass
            self.engine_black = None

    def request_redraw(self, hide_square=None):
        self.view.update_board(
            self.display_board, 
            self.selected_square, 
            self.viewing_history, 
            self.current_position_index,
            hide_square=hide_square
        )
        self.view.update_status(self.model.get_game_status_text())
        self.view.update_captured_display(self.model.captured_pieces_white, self.model.captured_pieces_black)

    def ask_engine_config(self, title):
        """Displays a dialog to select an engine and set its constraints."""
        dialog = tk.Toplevel(self.view.root)
        dialog.title(title)
        dialog.geometry("450x250")
        
        result_config = {}
        
        # Path
        tk.Label(dialog, text="Engine Executable:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        path_var = tk.StringVar()
        tk.Entry(dialog, textvariable=path_var, width=30).grid(row=0, column=1)
        def browse():
            filepath = filedialog.askopenfilename(filetypes=[("Executable", "*.exe"), ("All Files", "*.*")])
            if filepath: path_var.set(filepath)
        tk.Button(dialog, text="Browse", command=browse).grid(row=0, column=2, padx=5)
        
        # Depth
        tk.Label(dialog, text="Max Depth (empty = infinite):").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        depth_var = tk.StringVar(value="100")
        tk.Entry(dialog, textvariable=depth_var, width=15).grid(row=1, column=1, sticky="w")
        
        # Time
        tk.Label(dialog, text="Time Limit ms (empty = infinite):").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        time_var = tk.StringVar(value="100")
        tk.Entry(dialog, textvariable=time_var, width=15).grid(row=2, column=1, sticky="w")
        
        # Threads
        tk.Label(dialog, text="Threads (empty = engine default):").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        threads_var = tk.StringVar(value="1")
        tk.Entry(dialog, textvariable=threads_var, width=15).grid(row=3, column=1, sticky="w")
        
        def submit():
            if not path_var.get():
                messagebox.showerror("Error", "Please select an engine executable.", parent=dialog)
                return
                
            def parse_val(val):
                v = val.strip()
                return int(v) if v.isdigit() else None
                
            result_config['path'] = path_var.get()
            result_config['depth'] = parse_val(depth_var.get())
            result_config['time'] = parse_val(time_var.get())
            result_config['threads'] = parse_val(threads_var.get())
            dialog.destroy()
            
        tk.Button(dialog, text="Confirm Settings", command=submit, width=20).grid(row=4, column=0, columnspan=3, pady=20)
        
        dialog.grab_set()
        self.view.root.wait_window(dialog)
        
        return result_config if 'path' in result_config else None

    def _apply_engine_options(self, engine, config):
        if config['threads'] is not None:
            try:
                engine.configure({"Threads": config['threads']})
            except Exception as e:
                print(f"Notice: Engine doesn't support 'Threads' parameter. ({e})")

    def ask_game_mode(self):
        self._close_engines()
        
        self.view.root.withdraw() 
        
        choice_window = tk.Toplevel(self.view.root)
        choice_window.title("Select Game Mode")
        choice_window.geometry("300x200")
        
        choice_window.grab_set()
        
        self.mode_choice = None

        def set_mode(mode):
            self.mode_choice = mode
            choice_window.destroy()

        tk.Button(choice_window, text="Play against Bot", command=lambda: set_mode("pve")).pack(pady=10)
        tk.Button(choice_window, text="Engine vs Engine (Single Game)", command=lambda: set_mode("eve")).pack(pady=10)
        tk.Button(choice_window, text="Engine vs Engine (Tournament)", command=lambda: set_mode("tournament")).pack(pady=10)
        
        self.view.root.wait_window(choice_window) 
        
        if not self.mode_choice:
            self.quit_game()
            return 

        if self.mode_choice == "tournament":
            tourney_dialog = tk.Toplevel(self.view.root)
            tourney_dialog.title("Tournament Settings")
            tourney_dialog.geometry("300x150")
            tourney_dialog.grab_set()
            
            tk.Label(tourney_dialog, text="Number of Games:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
            games_var = tk.StringVar(value="100")
            tk.Entry(tourney_dialog, textvariable=games_var, width=10).grid(row=0, column=1, sticky="w")
            
            tk.Label(tourney_dialog, text="Concurrent Games:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
            concurrent_var = tk.StringVar(value="12")
            tk.Entry(tourney_dialog, textvariable=concurrent_var, width=10).grid(row=1, column=1, sticky="w")
            
            tourney_settings = {}
            
            def submit_tourney():
                try:
                    tourney_settings['games'] = int(games_var.get())
                    tourney_settings['concurrent'] = int(concurrent_var.get())
                    tourney_dialog.destroy()
                except ValueError:
                    messagebox.showerror("Invalid Input", "Please enter valid integers.", parent=tourney_dialog)
            
            tk.Button(tourney_dialog, text="Next", command=submit_tourney, width=15).grid(row=2, column=0, columnspan=2, pady=15)
            
            self.view.root.wait_window(tourney_dialog)
            
            if not tourney_settings:
                self.ask_game_mode()
                return
                
            num_games = tourney_settings['games']
            concurrent_games = tourney_settings['concurrent']
                
            white_cfg = self.ask_engine_config("Configure WHITE Engine")
            if not white_cfg: 
                self.ask_game_mode()
                return
                
            black_cfg = self.ask_engine_config("Configure BLACK Engine")
            if not black_cfg: 
                self.ask_game_mode()
                return
            
            runner = TournamentRunner(self.view.root, white_cfg, black_cfg, num_games=num_games, concurrent_games=concurrent_games)
            
            self.view.root.wait_window(runner.window)
            self.ask_game_mode()
                
        elif self.mode_choice == "eve":
            self.engine_vs_engine = True
            w_cfg = self.ask_engine_config("Configure WHITE Engine")
            if not w_cfg: 
                self.ask_game_mode()
                return
                
            b_cfg = self.ask_engine_config("Configure BLACK Engine")
            if not b_cfg: 
                self.ask_game_mode()
                return
            
            self.view.root.deiconify()
            self.config_white = w_cfg
            self.config_black = b_cfg
            
            self.engine_white = chess.engine.SimpleEngine.popen_uci(w_cfg['path'])
            self._apply_engine_options(self.engine_white, w_cfg)
            
            self.engine_black = chess.engine.SimpleEngine.popen_uci(b_cfg['path'])
            self._apply_engine_options(self.engine_black, b_cfg)
            
            self.model.player_color = None 
            self.make_bot_move()
            self.request_redraw()

        elif self.mode_choice == "pve":
            self.engine_vs_engine = False
            result = messagebox.askyesno("Color Selection", "Do you want to play as White?")
            self.model.set_colors(player_is_white=result)
            
            bot_cfg = self.ask_engine_config("Configure BOT Engine")
            if not bot_cfg:
                self.ask_game_mode()
                return
                
            self.view.root.deiconify()
            
            engine = chess.engine.SimpleEngine.popen_uci(bot_cfg['path'])
            self._apply_engine_options(engine, bot_cfg)
            
            if self.model.bot_color == chess.WHITE:
                self.config_white = bot_cfg
                self.engine_white = engine
            else:
                self.config_black = bot_cfg
                self.engine_black = engine

            if self.model.board.turn == self.model.bot_color:
                self.make_bot_move()
            self.request_redraw()

    def restart_game(self):
        self.model.reset()
        self._reset_view_state()
        
        self.view.rebuild_move_history_tree(self.model.board)
        self.view.depth_label.config(text="Depth: -")
        self.view.score_label.config(text="Score: -")
        
        self.update_navigation_buttons()
        self.ask_game_mode()

    def load_fen(self):
        fen = self.view.fen_entry.get().strip()
        try:
            self.model.load_fen(fen)
            self._reset_view_state()
            
            self.view.rebuild_move_history_tree(self.model.board)
            self.view.depth_label.config(text="Depth: -")
            self.view.score_label.config(text="Score: -")
            self.update_navigation_buttons()
            self.ask_game_mode()
        except ValueError as e:
            messagebox.showerror("Invalid FEN", f"The provided FEN is invalid: {str(e)}")

    def undo_move(self):
        if not self.model.board.move_stack:
            messagebox.showinfo("Cannot Undo", "No moves to undo.")
            return

        if self.model.board.turn == self.model.bot_color:
            self.model.board.pop()
        else:
            if len(self.model.board.move_stack) >= 2:
                self.model.board.pop()
                self.model.board.pop()
            else:
                self.model.board.pop()
                
        self.viewing_history = False
        self.current_position_index = -1
        self.display_board = self.model.board
        
        self.view.rebuild_move_history_tree(self.model.board)
        self.model.recalculate_captured_pieces()
        self.selected_square = None
        self.request_redraw()
        self.update_navigation_buttons()

    def handle_square_click(self, square):
        if getattr(self, 'engine_vs_engine', False) or self.model.board.turn != self.model.player_color:
            return
        if self.model.board.turn != self.model.player_color:
            return
            
        piece = self.model.board.piece_at(square)
        
        # 1. If clicking your own piece, select it (whether one is already selected or not)
        if piece and piece.color == self.model.player_color:
            self.selected_square = square
            self.request_redraw()
        # 2. If clicking an empty square or enemy piece, and we have a selection, try to move
        elif self.selected_square is not None:
            self.try_move(self.selected_square, square)

    # --- Interaction Logic ---
    def handle_drag_start(self, square, x, y):
        if getattr(self, 'engine_vs_engine', False) or self.model.board.turn != self.model.player_color: 
            return
        if self.model.board.turn != self.model.player_color: return
        piece = self.model.board.piece_at(square)
        if piece and piece.color == self.model.player_color:
            self.dragging = True
            self.selected_square = square
            self.drag_start_square = square
            self.request_redraw(hide_square=square)
            
            # Use image for the dragged piece
            symbol = piece.symbol()
            
            # Verify we are checking the view's dictionary!
            if hasattr(self.view, 'piece_images') and symbol in self.view.piece_images:
                self.view.drag_image_id = self.view.canvas.create_image(
                    x, y, image=self.view.piece_images[symbol]
                )
            else:
                # Fallback to text
                char_symbol = self.view.get_piece_symbol(piece)
                self.view.drag_image_id = self.view.canvas.create_text(
                    x, y, text=char_symbol, font=("Arial", 36), fill="#333333"
                )

    def handle_drag_end(self, target_square):
        if self.drag_start_square is not None and target_square is not None:
            self.try_move(self.drag_start_square, target_square)
        self.drag_start_square = None
        self.dragging = False

    def try_move(self, from_square, to_square):
        if from_square == to_square:
            self.request_redraw()
            return 
            
        move = chess.Move(from_square, to_square)
        piece = self.model.board.piece_at(from_square)
        
        if piece and piece.piece_type == chess.PAWN:
            if (self.model.player_color == chess.WHITE and to_square >= 56) or \
               (self.model.player_color == chess.BLACK and to_square <= 7):
                move.promotion = self.view.ask_promotion()
        
        if move in self.model.board.legal_moves:
            self.model.track_captured_piece(move)
            self.view.update_move_history_tree(self.model.board, move, is_white_move=True)
            self.model.board.push(move)
            self.selected_square = None
            self.request_redraw()
            self.update_navigation_buttons()
            
            if self.check_game_end(): return
            self.view.root.after(10, self.make_bot_move)
        else:
            self.selected_square = None
            self.request_redraw()

    def make_bot_move(self):
        if self.check_game_end(): return 
        
        is_white_turn = self.model.board.turn == chess.WHITE
        active_engine = self.engine_white if is_white_turn else self.engine_black
        engine_name = "White Engine" if is_white_turn else "Black Engine"
        active_config = self.config_white if is_white_turn else self.config_black
        
        self.view.status_label.config(text=f"Game Status: {engine_name} is thinking...") 
        
        board_copy = self.model.board.copy()
        
        bot_thread = threading.Thread(
            target=self._bot_calculation_thread, 
            args=(board_copy, active_engine, engine_name, active_config) 
        ) 
        bot_thread.daemon = True 
        bot_thread.start()

    def _bot_calculation_thread(self, board, engine, engine_name, config):
        try:
            start_time = time.time()
            
            time_limit_sec = (config['time'] / 1000.0) if config['time'] is not None else None
            limit = chess.engine.Limit(depth=config['depth'], time=time_limit_sec)
            
            result = engine.play(board, limit, info=chess.engine.INFO_ALL)
            
            calculation_time = time.time() - start_time
            actual_depth = result.info.get("depth", config['depth'] if config['depth'] is not None else "N/A") 
            
            print(f"[{engine_name}] Time: {calculation_time:.3f}s | Target Depth: {config['depth']} | Actual: {actual_depth} | Move: {result.move.uci()}")
            
            score_str = "N/A"
            if "score" in result.info:
                score = result.info["score"].white()
                if score.is_mate():
                    score_str = f"M{score.mate()}" 
                else:
                    val = score.score() / 100.0
                    score_str = f"{val:+.2f}" 

            move_info = {
                'move': result.move.uci(),
                'depth': actual_depth, 
                'score': score_str
            }
            
            self.view.root.after(0, self._apply_bot_move, move_info) 
            
        except Exception as e:
            print(f"[{engine_name}] Error: {e}")
            self.view.root.after(0, lambda: self.view.status_label.config(text="Game Status: Engine Error!"))

    def _reset_view_state(self):
        self.selected_square = None
        self.viewing_history = False
        self.current_position_index = -1
        self.display_board = self.model.board
    
    def _apply_bot_move(self, result):
        self.view.depth_label.config(text=f"Depth: {result['depth']}")
        self.view.score_label.config(text=f"Score: {result['score']}")
        
        move = chess.Move.from_uci(result['move'])
        self.model.track_captured_piece(move)
        
        is_white = self.model.board.turn == chess.WHITE
        self.view.update_move_history_tree(self.model.board, move, is_white_move=is_white)
        
        self.model.board.push(move)
        
        self.request_redraw()
        self.update_navigation_buttons()
        
        if not self.check_game_end():
            if getattr(self, 'engine_vs_engine', False):
                self.view.root.after(100, self.make_bot_move)

    # --- Time Travel Logic ---
    def go_to_move(self, move_index):
        if move_index == self.current_position_index: return
        
        temp_board = chess.Board()
        for i in range(min(move_index + 1, len(self.model.board.move_stack))):
            temp_board.push(self.model.board.move_stack[i])
            
        self.current_position_index = move_index
        self.viewing_history = (move_index < len(self.model.board.move_stack) - 1)
        self.display_board = temp_board
        self.request_redraw()
        self.update_navigation_buttons()

    def go_to_previous_move(self):
        if self.current_position_index > -1:
            self.go_to_move(self.current_position_index - 1)

    def go_to_next_move(self):
        if self.current_position_index < len(self.model.board.move_stack) - 1:
            self.go_to_move(self.current_position_index + 1)

    def return_to_present(self):
        if self.viewing_history:
            self.current_position_index = -1
            self.viewing_history = False
            self.display_board = self.model.board
            self.request_redraw()
            self.update_navigation_buttons()

    def update_navigation_buttons(self):
        self.view.prev_button.config(state=tk.DISABLED if self.current_position_index <= 0 else tk.NORMAL)
        self.view.next_button.config(state=tk.DISABLED if self.current_position_index >= len(self.model.board.move_stack) - 1 else tk.NORMAL)
        self.view.return_button.config(state=tk.NORMAL if self.viewing_history else tk.DISABLED)
        self.view.history_status.config(text="Viewing History" if self.viewing_history else "")

    def check_game_end(self):
        if self.model.board.is_game_over():
            messagebox.showinfo("Game Over", self.model.get_game_over_popup_text())
            return True
        return False
        
    def quit_game(self):
        self._close_engines()
        self.view.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    app = ChessController(root)
    root.protocol("WM_DELETE_WINDOW", app.quit_game)
    root.mainloop()