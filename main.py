import threading
import tkinter as tk
from tkinter import messagebox, filedialog
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
        
        self.depth_white = 100
        self.depth_black = 100

        self.ask_game_mode()
        
    def _close_engines(self):
        """Safely terminates active engines."""
        if getattr(self, 'engine_white', None):
            self.engine_white.quit()
            self.engine_white = None
        if getattr(self, 'engine_black', None):
            self.engine_black.quit()
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

    def ask_game_mode(self):
        self._close_engines()
        
        # Create a custom dialog for the 3 choices
        choice_window = tk.Toplevel(self.view.root)
        choice_window.title("Select Game Mode")
        choice_window.geometry("300x200")
        
        self.mode_choice = None

        def set_mode(mode):
            self.mode_choice = mode
            choice_window.destroy()

        tk.Button(choice_window, text="Play against Bot", command=lambda: set_mode("pve")).pack(pady=10)
        tk.Button(choice_window, text="Engine vs Engine (Single Game)", command=lambda: set_mode("eve")).pack(pady=10)
        tk.Button(choice_window, text="Engine vs Engine (100 Games Stats)", command=lambda: set_mode("tournament")).pack(pady=10)
        
        self.view.root.wait_window(choice_window) # Wait for user to click
        
        if not self.mode_choice:
            return # User closed window

        if self.mode_choice == "tournament":
            messagebox.showinfo("Tournament Mode", "Select engines: White, then Black.")
            white_path = filedialog.askopenfilename(title="Select WHITE Engine", filetypes=[("Executable", "*.exe")])
            black_path = filedialog.askopenfilename(title="Select BLACK Engine", filetypes=[("Executable", "*.exe")])
            
            if white_path and black_path:
                # Trigger the separate file logic
                TournamentRunner(self.view.root, white_path, black_path, num_games=100, depth=100)
                # Keep main board empty or reset
                self.model.reset()
                self.request_redraw()
                
        elif self.mode_choice == "eve":
            self.engine_vs_engine = True
            white_path = filedialog.askopenfilename(title="Select WHITE Engine", filetypes=[("Executable", "*.exe")])
            black_path = filedialog.askopenfilename(title="Select BLACK Engine", filetypes=[("Executable", "*.exe")])
            
            if white_path and black_path:
                self.engine_white = chess.engine.SimpleEngine.popen_uci(white_path)
                self.engine_black = chess.engine.SimpleEngine.popen_uci(black_path)
                self.model.player_color = None 
                self.make_bot_move()
                self.request_redraw()

        elif self.mode_choice == "pve":
            self.engine_vs_engine = False
            result = messagebox.askyesno("Color Selection", "Do you want to play as White?")
            self.model.set_colors(player_is_white=result)
            
            bot_path = filedialog.askopenfilename(title="Select BOT Engine", filetypes=[("Executable", "*.exe")])
            if bot_path:
                if self.model.bot_color == chess.WHITE:
                    self.engine_white = chess.engine.SimpleEngine.popen_uci(bot_path)
                else:
                    self.engine_black = chess.engine.SimpleEngine.popen_uci(bot_path)

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

    # --- Bot Logic ---
    def make_bot_move(self):
        if self.check_game_end(): return 
        
        is_white_turn = self.model.board.turn == chess.WHITE
        active_engine = self.engine_white if is_white_turn else self.engine_black
        engine_name = "White Engine" if is_white_turn else "Black Engine"
        
        # Select the corresponding depth limit
        active_depth = self.depth_white if is_white_turn else self.depth_black
        
        self.view.status_label.config(text=f"Game Status: {engine_name} is thinking...") 
        
        board_copy = self.model.board.copy()
        
        bot_thread = threading.Thread(
            target=self._bot_calculation_thread, 
            # Add active_depth to the arguments
            args=(board_copy, active_engine, engine_name, active_depth) 
        ) 
        bot_thread.daemon = True 
        bot_thread.start()

    def _bot_calculation_thread(self, board, engine, engine_name, depth_limit):
        try:
            start_time = time.time()
            
            result = engine.play(
                board, 
                chess.engine.Limit(depth=depth_limit), 
                info=chess.engine.INFO_ALL
            )
            
            calculation_time = time.time() - start_time
            actual_depth = result.info.get("depth", depth_limit) 
            
            print(f"[{engine_name}] Time: {calculation_time:.3f}s | Target Depth: {depth_limit} | Actual: {actual_depth} | Move: {result.move.uci()}")
            
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
    app = ChessController(root)
    root.protocol("WM_DELETE_WINDOW", app.quit_game)
    root.mainloop()