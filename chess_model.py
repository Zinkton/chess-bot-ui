import chess

class ChessModel:
    def __init__(self):
        self.board = chess.Board()
        self.player_color = None
        self.bot_color = None
        self.captured_pieces_white = []
        self.captured_pieces_black = []

    def reset(self):
        self.board = chess.Board()
        self.captured_pieces_white.clear()
        self.captured_pieces_black.clear()

    def load_fen(self, fen):
        self.board = chess.Board(fen)
        self.captured_pieces_white.clear()
        self.captured_pieces_black.clear()

    def set_colors(self, player_is_white):
        if player_is_white:
            self.player_color = chess.WHITE
            self.bot_color = chess.BLACK
        else:
            self.player_color = chess.BLACK
            self.bot_color = chess.WHITE

    def track_captured_piece(self, move):
        if self.board.is_en_passant(move):
            captured_pawn = chess.Piece(chess.PAWN, not self.board.turn)
            if captured_pawn.color == chess.WHITE: 
                self.captured_pieces_black.append(captured_pawn)
            else: 
                self.captured_pieces_white.append(captured_pawn)
            return

        captured_piece = self.board.piece_at(move.to_square)
        if captured_piece:
            if captured_piece.color == chess.WHITE: 
                self.captured_pieces_black.append(captured_piece)
            else: 
                self.captured_pieces_white.append(captured_piece)

    def recalculate_captured_pieces(self):
        self.captured_pieces_white.clear()
        self.captured_pieces_black.clear()
        temp_board = chess.Board()
        
        for move in self.board.move_stack:
            if temp_board.is_en_passant(move):
                captured = chess.Piece(chess.PAWN, not temp_board.turn)
                if captured.color == chess.WHITE: 
                    self.captured_pieces_black.append(captured)
                else: 
                    self.captured_pieces_white.append(captured)
            else:
                captured = temp_board.piece_at(move.to_square)
                if captured:
                    if captured.color == chess.WHITE: 
                        self.captured_pieces_black.append(captured)
                    else: 
                        self.captured_pieces_white.append(captured)
            temp_board.push(move)

    def get_game_status_text(self):
        if self.board.is_game_over():
            if self.board.is_checkmate(): return "Checkmate!"
            elif self.board.is_stalemate(): return "Stalemate"
            elif self.board.is_insufficient_material(): return "Draw (Insufficient Material)"
            return "Draw"
        elif self.board.is_check():
            return "Check!"
        return "In Progress"

    def get_game_over_popup_text(self):
        if self.board.is_checkmate():
            winner = "Black" if self.board.turn == chess.WHITE else "White"
            return f"{winner} wins by checkmate!"
        elif self.board.is_stalemate(): return "Draw by stalemate"
        elif self.board.is_insufficient_material(): return "Draw by insufficient material"
        elif self.board.is_fifty_moves(): return "Draw by fifty-move rule"
        elif self.board.is_repetition(): return "Draw by repetition"
        return "Draw"