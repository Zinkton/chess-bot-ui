import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import chess
from PIL import Image, ImageTk

class ChessView:
    SQUARE_SIZE = 60
    COLOR_LIGHT = "#f0d9b5"
    COLOR_DARK = "#b58863"
    COLOR_MOVE_INDICATOR = "#00aa00"
    COLOR_CAPTURE_INDICATOR = "#aa5500"
    COLOR_LAST_MOVE = "#aaaa00"
    COLOR_SELECTION = "#00aa00"
    COLOR_CHECK = "#cc0000"

    def __init__(self, root, controller):
        self.root = root
        self.controller = controller
        self.root.title("Chess Game")
        self.root.geometry("900x800")
        
        self.board_flipped = False
        self.drag_image_id = None
        self.legal_move_indicators = []
        
        self.piece_images = {}
        self.load_images()
        
        self.setup_ui()
        
    def load_images(self):
        """Slices the 2x6 sprite sheet into individual piece images."""
        try:
            # Load the sprite sheet (ensure it's a PNG in your directory)
            sprite_sheet = Image.open("Chess_Pieces_Sprite.png")
            sheet_width, sheet_height = sprite_sheet.size
            
            # The image has 6 columns and 2 rows
            piece_width = sheet_width // 6
            piece_height = sheet_height // 2
            
            # Column mapping based on the image: King, Queen, Bishop, Knight, Rook, Pawn
            columns = {'k': 0, 'q': 1, 'b': 2, 'n': 3, 'r': 4, 'p': 5}
            
            for piece_char, col in columns.items():
                left = col * piece_width
                right = left + piece_width
                
                # Row 0 (Top) is White: Python-Chess uses uppercase symbols (K, Q, B...)
                upper_white = 0
                lower_white = piece_height
                img_white = sprite_sheet.crop((left, upper_white, right, lower_white))
                img_white = img_white.resize((self.SQUARE_SIZE, self.SQUARE_SIZE), Image.Resampling.LANCZOS)
                self.piece_images[piece_char.upper()] = ImageTk.PhotoImage(img_white)
                
                # Row 1 (Bottom) is Black: Python-Chess uses lowercase symbols (k, q, b...)
                upper_black = piece_height
                lower_black = sheet_height
                img_black = sprite_sheet.crop((left, upper_black, right, lower_black))
                img_black = img_black.resize((self.SQUARE_SIZE, self.SQUARE_SIZE), Image.Resampling.LANCZOS)
                self.piece_images[piece_char] = ImageTk.PhotoImage(img_black)
                
        except Exception as e:
            print(f"Warning: Could not load piece graphics. Using text fallback. Error: {e}")

    def _square_to_display_coords(self, square):
        row = square // 8
        col = square % 8
        display_row = 7 - row if not self.board_flipped else row
        display_col = col if not self.board_flipped else 7 - col
        return display_col * self.SQUARE_SIZE, display_row * self.SQUARE_SIZE

    def _display_coords_to_square(self, x, y):
        display_col = x // self.SQUARE_SIZE
        display_row = y // self.SQUARE_SIZE
        if display_col < 0 or display_col > 7 or display_row < 0 or display_row > 7:
            return None
        col = display_col if not self.board_flipped else 7 - display_col
        row = 7 - display_row if not self.board_flipped else display_row
        return row * 8 + col

    def setup_ui(self):
        main_container = tk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        left_panel = tk.Frame(main_container)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=10, pady=10)
        
        right_panel = tk.Frame(main_container)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.board_frame = tk.Frame(left_panel)
        self.board_frame.pack(pady=10)
        
        canvas_size = self.SQUARE_SIZE * 8
        self.canvas = tk.Canvas(self.board_frame, width=canvas_size, height=canvas_size)
        self.canvas.pack()
        
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<ButtonPress-1>", self.on_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
        self.info_frame = tk.Frame(left_panel)
        self.info_frame.pack(pady=5, fill=tk.X)
        self.status_label = tk.Label(self.info_frame, text="Game Status: In Progress", font=("Arial", 12))
        self.status_label.pack(side=tk.LEFT, padx=10)
        self.turn_label = tk.Label(self.info_frame, text="Turn: White", font=("Arial", 12))
        self.turn_label.pack(side=tk.RIGHT, padx=10)
        self.history_status = tk.Label(self.info_frame, text="", font=("Arial", 10), fg="blue")
        self.history_status.pack(side=tk.RIGHT, padx=10)
        
        self.bot_frame = tk.Frame(left_panel)
        self.bot_frame.pack(pady=5, fill=tk.X)
        self.depth_label = tk.Label(self.bot_frame, text="Depth: -", font=("Arial", 10))
        self.depth_label.pack(side=tk.LEFT, padx=10)
        self.score_label = tk.Label(self.bot_frame, text="Score: -", font=("Arial", 10))
        self.score_label.pack(side=tk.LEFT, padx=10)
        
        self.captured_frame = tk.Frame(left_panel)
        self.captured_frame.pack(pady=5, fill=tk.X)
        
        white_captured_frame = tk.Frame(self.captured_frame)
        white_captured_frame.pack(side=tk.TOP, fill=tk.X, pady=2)
        tk.Label(white_captured_frame, text="White captured: ", font=("Arial", 10)).pack(side=tk.LEFT)
        self.white_captured_label = tk.Label(white_captured_frame, text="", font=("Arial", 18))
        self.white_captured_label.pack(side=tk.LEFT)
        
        black_captured_frame = tk.Frame(self.captured_frame)
        black_captured_frame.pack(side=tk.TOP, fill=tk.X, pady=2)
        tk.Label(black_captured_frame, text="Black captured: ", font=("Arial", 10)).pack(side=tk.LEFT)
        self.black_captured_label = tk.Label(black_captured_frame, text="", font=("Arial", 18))
        self.black_captured_label.pack(side=tk.LEFT)
        
        control_panel = tk.Frame(left_panel)
        control_panel.pack(pady=10, fill=tk.X)
        
        controls_row1 = tk.Frame(control_panel)
        controls_row1.pack(fill=tk.X, pady=5)
        tk.Button(controls_row1, text="Restart Game", command=self.controller.restart_game).pack(side=tk.LEFT, padx=5)
        tk.Button(controls_row1, text="Flip Board", command=self.flip_board).pack(side=tk.LEFT, padx=5)
        tk.Button(controls_row1, text="Undo Move", command=self.controller.undo_move).pack(side=tk.LEFT, padx=5)
        
        fen_frame = tk.Frame(control_panel)
        fen_frame.pack(fill=tk.X, pady=5)
        tk.Label(fen_frame, text="FEN:").pack(side=tk.LEFT)
        self.fen_entry = tk.Entry(fen_frame, width=40)
        self.fen_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Button(fen_frame, text="Load", command=self.controller.load_fen).pack(side=tk.LEFT)
        
        history_frame = tk.Frame(right_panel)
        history_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(history_frame, text="Move History", font=("Arial", 12, "bold")).pack(pady=5)
        
        columns = ('move', 'white', 'black')
        self.move_tree = ttk.Treeview(history_frame, columns=columns, show='headings')
        self.move_tree.heading('move', text='#')
        self.move_tree.heading('white', text='White')
        self.move_tree.heading('black', text='Black')
        self.move_tree.column('move', width=50, anchor=tk.CENTER)
        self.move_tree.column('white', width=100, anchor=tk.CENTER)
        self.move_tree.column('black', width=100, anchor=tk.CENTER)
        self.move_tree.bind("<ButtonRelease-1>", self.on_move_history_click)
        
        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.move_tree.yview)
        self.move_tree.configure(yscroll=scrollbar.set)
        self.move_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        nav_frame = tk.Frame(history_frame)
        nav_frame.pack(side=tk.BOTTOM, pady=10)
        self.prev_button = tk.Button(nav_frame, text="◀", width=5, command=self.controller.go_to_previous_move, state=tk.DISABLED)
        self.prev_button.pack(side=tk.LEFT, padx=5)
        self.return_button = tk.Button(nav_frame, text="Present", width=8, command=self.controller.return_to_present, state=tk.DISABLED)
        self.return_button.pack(side=tk.LEFT, padx=5)
        self.next_button = tk.Button(nav_frame, text="▶", width=5, command=self.controller.go_to_next_move, state=tk.DISABLED)
        self.next_button.pack(side=tk.LEFT, padx=5)

    def update_board(self, board, selected_square=None, viewing_history=False, current_position_index=-1, hide_square=None):
        self.canvas.delete("all")
        self.legal_move_indicators = []
        colors = [self.COLOR_LIGHT, self.COLOR_DARK]
        
        white_king_in_check = board.is_check() and board.turn == chess.WHITE
        black_king_in_check = board.is_check() and board.turn == chess.BLACK
        
        for square in range(64):
            x1, y1 = self._square_to_display_coords(square)
            x2 = x1 + self.SQUARE_SIZE
            y2 = y1 + self.SQUARE_SIZE
            
            row = square // 8
            col = square % 8
            color_idx = (row + col + 1) % 2
            
            # 1. Draw square
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=colors[color_idx], outline="")
            
            # Skip drawing the piece if it's the one we are currently dragging!
            if square == hide_square:
                continue
            
            # 2. Draw piece FIRST
            piece = board.piece_at(square)
            if piece:
                symbol = piece.symbol() # e.g., 'P', 'k', 'N'
                is_king_in_check = piece.piece_type == chess.KING and \
                                   ((piece.color == chess.WHITE and white_king_in_check) or
                                    (piece.color == chess.BLACK and black_king_in_check))
                
                # If king is in check, draw a red background behind the piece
                if is_king_in_check:
                    self.canvas.create_rectangle(
                        x1, y1, x2, y2, fill=self.COLOR_CHECK, outline=""
                    )

                # --- NEW: Draw the image instead of text ---
                if self.piece_images and symbol in self.piece_images:
                    self.canvas.create_image(
                        x1 + self.SQUARE_SIZE//2, y1 + self.SQUARE_SIZE//2, 
                        image=self.piece_images[symbol]
                    )
                else:
                    # Fallback to text if image didn't load
                    char_symbol = self.get_piece_symbol(piece)
                    piece_color = "white" if is_king_in_check else "black"
                    self.canvas.create_text(
                        x1 + self.SQUARE_SIZE//2, y1 + self.SQUARE_SIZE//2, 
                        text=char_symbol, font=("Arial", 36), fill=piece_color
                    )

            # 3. Draw coordinates LAST
            # ... (Keep your existing coordinate drawing code here exactly as it was) ...
            text_color = self.COLOR_DARK if color_idx == 0 else self.COLOR_LIGHT
            display_row = 7 - row if not self.board_flipped else row
            display_col = col if not self.board_flipped else 7 - col
            
            if display_col == 0:
                self.canvas.create_text(
                    x1 + 3, y1 + 3, text=str(row + 1), font=("Arial", 10, "bold"), anchor=tk.NW, fill=text_color
                )
            if display_row == 7:
                self.canvas.create_text(
                    x2 - 3, y2 - 3, text=chr(97 + col), font=("Arial", 10, "bold"), anchor=tk.SE, fill=text_color
                )
        
        # Highlights
        if selected_square is not None and not viewing_history:
            self.show_legal_moves(board, selected_square)
            x1, y1 = self._square_to_display_coords(selected_square)
            self.canvas.create_rectangle(
                x1, y1, x1 + self.SQUARE_SIZE, y1 + self.SQUARE_SIZE, 
                outline=self.COLOR_SELECTION, width=3
            )
                
        if board.move_stack:
            last_move = board.move_stack[current_position_index] if viewing_history and current_position_index >= 0 else board.peek()
            for sq in [last_move.from_square, last_move.to_square]:
                x1, y1 = self._square_to_display_coords(sq)
                self.canvas.create_rectangle(
                    x1, y1, x1 + self.SQUARE_SIZE, y1 + self.SQUARE_SIZE, 
                    outline=self.COLOR_LAST_MOVE, width=3
                )
        
        # Labels
        self.turn_label.config(text=f"Turn: {'White' if board.turn == chess.WHITE else 'Black'}")
        self.fen_entry.delete(0, tk.END)
        self.fen_entry.insert(0, board.fen())

    def update_status(self, status_text):
        self.status_label.config(text=f"Game Status: {status_text}")

    def update_captured_display(self, captured_white, captured_black):
        self.white_captured_label.config(text=' '.join([self.get_piece_symbol(p) for p in captured_white]))
        self.black_captured_label.config(text=' '.join([self.get_piece_symbol(p) for p in captured_black]))

    def show_legal_moves(self, board, from_square):
        for move in board.legal_moves:
            if move.from_square == from_square:
                x, y = self._square_to_display_coords(move.to_square)
                center_x, center_y = x + self.SQUARE_SIZE // 2, y + self.SQUARE_SIZE // 2
                
                if board.piece_at(move.to_square) or board.is_en_passant(move):
                    indicator = self.canvas.create_oval(
                        center_x - 25, center_y - 25, center_x + 25, center_y + 25,
                        outline=self.COLOR_CAPTURE_INDICATOR, width=3
                    )
                else:
                    indicator = self.canvas.create_oval(
                        center_x - 10, center_y - 10, center_x + 10, center_y + 10,
                        fill=self.COLOR_MOVE_INDICATOR, outline=""
                    )
                self.legal_move_indicators.append(indicator)

    def get_piece_symbol(self, piece):
        return {'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'Q': '♕', 'K': '♔',
                'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛', 'k': '♚'}[piece.symbol()]

    def ask_promotion(self):
        options = {"Queen": chess.QUEEN, "Rook": chess.ROOK, "Bishop": chess.BISHOP, "Knight": chess.KNIGHT}
        choice = simpledialog.askstring("Promotion", "Choose promotion piece (Queen, Rook, Bishop, Knight):", initialvalue="Queen")
        if choice and choice.title() in options:
            return options[choice.title()]
        return chess.QUEEN

    def update_move_history_tree(self, board, move, is_white_move):
        san_move = board.san(move)
        move_number = (len(board.move_stack)) // 2 + 1
        
        if not is_white_move:
            last_item = self.move_tree.get_children()[-1]
            current_values = self.move_tree.item(last_item, 'values')
            self.move_tree.item(last_item, values=(current_values[0], current_values[1], san_move))
        else:
            self.move_tree.insert('', 'end', values=(move_number, san_move, ''))
            
        if self.move_tree.get_children():
            self.move_tree.see(self.move_tree.get_children()[-1])

    def rebuild_move_history_tree(self, board):
        for item in self.move_tree.get_children():
            self.move_tree.delete(item)
            
        temp_board = chess.Board()
        for i, move in enumerate(board.move_stack):
            san_move = temp_board.san(move)
            temp_board.push(move)
            move_number = (i // 2) + 1
            is_white_move = (i % 2 == 0)
            
            if is_white_move:
                self.move_tree.insert('', 'end', values=(move_number, san_move, ''))
            else:
                last_item = self.move_tree.get_children()[-1]
                current_values = self.move_tree.item(last_item, 'values')
                self.move_tree.item(last_item, values=(current_values[0], current_values[1], san_move))
                
        if self.move_tree.get_children():
            self.move_tree.see(self.move_tree.get_children()[-1])

    def flip_board(self):
        self.board_flipped = not self.board_flipped
        self.controller.request_redraw()

    # --- Mouse Events Routed to Controller ---
    def on_canvas_click(self, event):
        if self.controller.viewing_history:
            self.controller.return_to_present()
            return "break"

    def on_drag_start(self, event):
        if self.controller.viewing_history:
            self.controller.return_to_present()
            return "break"
        square = self._display_coords_to_square(event.x, event.y)
        if square is not None:
            self.controller.handle_drag_start(square, event.x, event.y)

    def on_drag_motion(self, event):
        if self.drag_image_id:
            self.canvas.itemconfig(self.drag_image_id, state=tk.NORMAL)
            self.canvas.coords(self.drag_image_id, event.x, event.y)

    def on_drag_end(self, event):
        if self.drag_image_id:
            self.canvas.delete(self.drag_image_id)
            self.drag_image_id = None
            target_square = self._display_coords_to_square(event.x, event.y)
            self.controller.handle_drag_end(target_square)

    def on_release(self, event):
        if self.controller.dragging:
            self.on_drag_end(event)
        else:
            square = self._display_coords_to_square(event.x, event.y)
            if square is not None:
                self.controller.handle_square_click(square)

    def on_move_history_click(self, event):
        selected_item = self.move_tree.focus()
        if not selected_item: return
        values = self.move_tree.item(selected_item, 'values')
        if not values: return
        
        item_index = self.move_tree.get_children().index(selected_item)
        move_index = item_index * 2
        
        region = self.move_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.move_tree.identify_column(event.x)
            if column == "#3" and values[2]: move_index += 1
                
        self.controller.go_to_move(move_index)