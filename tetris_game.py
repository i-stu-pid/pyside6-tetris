# -*- coding: utf-8 -*-


"""俄罗斯方块 游戏运行
显示部件下落、移动、旋转、堆积、消除
"""


# 模块信息
__all__ = ['TetrisGame']
__version__ = '0.1'
__author__ = 'lihua.tan'


# python库
from enum import IntEnum
from typing import override
# Qt标准库
from PySide6.QtCore import (Qt, Slot, QBasicTimer, QTimerEvent, QEvent, QObject)
from PySide6.QtGui import (QKeyEvent)
from PySide6.QtWidgets import (QWidget, QMessageBox)
# 自封装库
from ini_config import GlobalConfig# 配置文件管理
from drag_resize import DragResize# 调整大小
from tetris_board import BoardSquare# 游戏面板
from tetris_piece import TetrisPiece, Shape# 游戏部件
from tetris_game_ui import Ui_Form# ui界面


# 部件变换
class TransferOption(IntEnum):
    '''部件变换
    '''
    _None = 0# 无
    LineDown = Qt.Key.Key_L# 下移一行
    DropDown = Qt.Key.Key_Down# 落至底部
    LeftShift = Qt.Key.Key_Left# 左移
    RightShift = Qt.Key.Key_Right# 右移
    Rotate = Qt.Key.Key_Up# 顺时针旋转


# 游戏运行状态
class GameState(IntEnum):
    '''游戏运行状态
    '''
    End = 0,# 结束
    Run = 1,# 运行
    Pause = 2,# 暂停


class TetrisData(object):
    '''俄罗斯方块 游戏数据
    '''
    def __init__(self, ui: Ui_Form) -> None:
        '''构造
        '''
        self.__ui = ui# 控制界面
        self.load_config()# 加载配置
        self.reset()# 重置数据

    def load_config(self) -> None:
        '''加载配置
        '''
        # 初始等级
        self.__start_level = 1
        load_value = GlobalConfig.load(__name__, 'start_level', str(self.__start_level))
        self.__start_level = int(load_value)
        # 达到此值, 等级+1
        self.__update_level_count = 25
        load_value = GlobalConfig.load(__name__, 'update_level_count', str(self.__update_level_count))
        self.__update_level_count = int(load_value)

    def save_config(self) -> None:
        '''保存配置
        '''
        # 初始等级
        GlobalConfig.save(__name__, 'start_level', str(self.__start_level))
        # 达到此值, 等级+1
        GlobalConfig.save(__name__, 'update_level_count', str(self.__update_level_count))

    def reset(self) -> None:
        '''重置
        '''
        # 重置数据
        self._score = 0# 分数
        self._level = self.__start_level# 等级
        self._lines_removed = 0# 累计移除行数
        self._pieces_dropped = 0# 累计下落部件

    def display(self) -> None:
        '''显示数据
        '''
        self.__ui.lcdNumber_score.display(self._score)# 分数
        self.__ui.lcdNumber_level.display(self._level)# 等级
        self.__ui.lcdNumber_removed_lines.display(self._lines_removed)# 累计移除行数

    def update(self, remove_lines: int) -> None:
        '''更新数据
        '''
        # 放置部件
        self._score += 1# 分数
        self._pieces_dropped += 1# 累计下落部件
        if self._pieces_dropped % self.__update_level_count == 0:
            self._level += 1# 等级
        # 消除整行
        if remove_lines:
            self._score += 10 * remove_lines# 分数
            self._lines_removed += remove_lines# 累计移除行数


# 游戏运行
class TetrisGame(QWidget):
    '''俄罗斯方块 游戏运行
    '''
    def __init__(self, parent=None) -> None:
        '''构造
        '''
        # 访问父类的方法和属性
        super().__init__(parent)
        # 配置
        GlobalConfig.load_file(base_name='俄罗斯方块配置')
        self.load_config()# 加载配置
        # 界面
        self.__ui = Ui_Form()
        self.__ui.setupUi(self)
        self.__ui.frame_board.raise_()
        self.setWindowTitle('俄罗斯方块')# 标题
        # 数据
        self.__data = TetrisData(self.__ui)
        self.__data.display()
        # 面板
        self._board = self.__ui.frame_board
        self._board.reset(self.__board_row_count, self.__board_col_count)
        # 当前部件
        self._curr_piece = TetrisPiece()
        # 下一部件
        self._next_piece = TetrisPiece()
        self._next_piece.set_random_shape()
        self._next_piece_label = self.__ui.label_next_piece
        self._next_piece_label.installEventFilter(self)
        # 运行
        self._timer = QBasicTimer()# 定时器 (定时移动部件)
        self._state = GameState.End# 状态
        self.__ui.pushButton_start.clicked.connect(self.start)# 开始
        self.__ui.pushButton_recover.clicked.connect(self.start)# 恢复
        self.__ui.pushButton_pause.clicked.connect(self.pause)# 暂停
        self.__ui.pushButton_end.clicked.connect(self.end)# 结束
        # 窗口大小
        self.__init_size()
        self.installEventFilter(self)# 事件监听

    def __init_size(self) -> None:
        '''设置窗口大小
        '''
        # 面板
        board_widget = self._board.get_col_count() * self.__square_width
        board_height = self._board.get_row_count() * self.__square_height
        self._board_scale = board_widget / board_height
        # 窗口
        self._board_to_widget_hor = 3 / (2 + 3 + 2)# 水平布局比例
        widget_widget = board_widget / self._board_to_widget_hor
        widget_height = board_height
        # 调整大小
        self.setFixedSize(widget_widget, widget_height)
        self._darg_resize = DragResize(self, scale=True)# 比例调整大小
        self._darg_resize.set_size_adjust_callback(self.get_size_perfect_adjust)# 回调

    def get_size_perfect_adjust(self, width_adjust: int, height_adjust: int) -> list[int]:
        '''最优调整
        大小调整需以面板为基础
        '''
        # 转为面板调整
        board_width_adjust = width_adjust * self._board_to_widget_hor
        board_height_adjust = height_adjust
        adjust_scale = board_width_adjust / board_height_adjust
        # 以宽度为基准
        if adjust_scale > self._board_scale:
            board_height_adjust = board_width_adjust / self._board_scale
        # 以高度为基准
        else:
            board_width_adjust = board_height_adjust * self._board_scale
        # 最优调整
        width_adjust = board_width_adjust / self._board_to_widget_hor
        height_adjust = board_height_adjust
        return [width_adjust, height_adjust]

    def load_config(self) -> None:
        '''加载配置
        '''
        # 面板行数
        load_value = GlobalConfig.load(__name__, 'board_row_count', '24')
        self.__board_row_count = int(load_value)
        # 面板列数
        load_value = GlobalConfig.load(__name__, 'board_col_count', '10')
        self.__board_col_count = int(load_value)
        # 方块宽度
        load_value = GlobalConfig.load(__name__, 'square_width', '27')
        self.__square_width = int(load_value)
        # 方块高度
        load_value = GlobalConfig.load(__name__, 'square_height', '27')
        self.__square_height = int(load_value)

    def save_config(self) -> None:
        '''保存配置
        '''
        # 初始等级
        GlobalConfig.save(__name__, 'board_row_count', str(self.__board_row_count))
        # 达到此值, 等级+1
        GlobalConfig.save(__name__, 'board_col_count', str(self.__board_col_count))
        # 方块大小
        GlobalConfig.save(__name__, 'square_width', str(self.__square_width))
        # 方块大小
        GlobalConfig.save(__name__, 'square_height', str(self.__square_height))

    def set_timer_start(self, enable: bool, time_ms=-1) -> None:
        '''定时设置
        '''
        if not enable or self._state == GameState.End:
            self._timer.stop()
            return None
        if time_ms == -1:
            time_ms = 1000 / self.__data._level
        self._timer.start(time_ms, self)

    @Slot()# 槽
    def start(self) -> None:
        '''开始游戏
        '''
        # 开始
        if self._state == GameState.End:
            if self._state == GameState.Run:
                self.set_timer_start(False)
                if QMessageBox.StandardButton.Yes != QMessageBox.question(self, '提示', '游戏运行中, 确定重新开始游戏?'):
                    self.set_timer_start(True)
                    return None
            self.__data.reset()# 数据
            self.__data.display()
            self._board.clear_all()# 面板
            self.get_new_piece()# 部件
            self._state = GameState.Run# 状态
            self.update()
        # 恢复
        elif self._state == GameState.Pause:
            if self._state == GameState.Run:
                QMessageBox.information(self, '提示', '游戏运行中')
                return None
            if self._state == GameState.End:
                QMessageBox.information(self, '提示', '游戏已结束')
                return None
            self._state = GameState.Run# 状态
        # 定时器
        self.set_timer_start(True)
        self._board.setFocus()# 设置焦点到面板, 快速响应键盘按键处理

    @Slot()# 槽
    def pause(self) -> None:
        '''暂停游戏
        '''
        if self._state == GameState.Run:# 必须在运行状态
            self.set_timer_start(False)# 定时器
            self._state = GameState.Pause# 状态
            self.update()# 更新界面
        if self._state == GameState.Pause:
            QMessageBox.information(self, '提示', '游戏已暂停')

    @Slot()# 槽
    def end(self) -> None:
        '''结束游戏
        '''
        self.set_timer_start(False)# 定时器
        self._state = GameState.End# 状态
        self.update()# 更新界面
        if self._state == GameState.End:
            QMessageBox.information(self, '提示', '游戏已结束')

    @override# 重写
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        '''事件监控器
        '''
        event_type = event.type()
        # 关闭
        if event_type == QEvent.Type.Close:
            self.save_config()
            self.__data.save_config()
            GlobalConfig.save_to_file()
        # 绘制
        if event_type == QEvent.Type.Paint:
            # 调整方块大小
            self._board.adjust_square_size()
            self.__square_width = int(BoardSquare._width)
            self.__square_height = int(BoardSquare._height)
            # 绘制下一部件
            if watched == self._next_piece_label:
                if self._next_piece.get_shape() != Shape._None:
                    self._next_piece.draw(self._next_piece_label)# 绘制部件
            # 面板绘制在 tetris_board.py 中
        # 键盘按下
        elif event_type == QEvent.Type.KeyPress:
            key_event: QKeyEvent = event
            # 部件变换
            option = self.key_to_option(key_event.key())
            if option != TransferOption._None:
                self.try_transfer_piece(option)
        # 定时器
        elif event_type == QEvent.Type.Timer:
            timer_event: QTimerEvent = event
            # 定时移动
            if timer_event.timerId() == self._timer.timerId():
                self.try_transfer_piece(TransferOption.LineDown)
                self.set_timer_start(False if self._state == GameState.End else True)
        return super(TetrisGame, self).eventFilter(watched, event)
    
    def key_to_option(self, key_value: int) -> TransferOption:
        '''键值 转为 变换操作
        '''
        try:
            return TransferOption(key_value)
        except:
            return TransferOption._None

    def get_new_piece(self) -> bool:
        '''更新部件
        '''
        # 取下一部件
        new_piece = self._next_piece.transfer(0, -(1 + self._next_piece.get_top_y()))# 确保整个进入
        if not self._board.is_piece_setable(new_piece):# 尝试放置
            self._board.set_draw_piece(None)
            self.end()# 结束运行
            return False
        # 更新部件
        self._curr_piece = new_piece
        self._next_piece.set_random_shape()
        self._board.set_draw_piece(self._curr_piece)
        return True

    def transfer_piece(self, option: TransferOption) -> TetrisPiece:
        '''部件变换
        '''
        # 无
        if option == TransferOption._None:
            return self._curr_piece
        # 下移一行
        if option == TransferOption.LineDown:
            new_piece = self._curr_piece.transfer(0, -1)
        # 落至底部
        elif option == TransferOption.DropDown:
            new_piece = self._curr_piece.transfer(0, -1)
            while self._board.is_piece_setable(new_piece):
                new_piece = new_piece.transfer(0, -1)
            self._curr_piece = new_piece.transfer(0, 1)
        # 左移
        elif option == TransferOption.LeftShift:
            new_piece = self._curr_piece.transfer(-1, 0)
        # 右移
        elif option == TransferOption.RightShift:
            new_piece = self._curr_piece.transfer(1, 0)
        # 顺时针旋转90度
        elif option == TransferOption.Rotate:
            new_piece = self._curr_piece.transfer(angle=90)
        return new_piece

    def try_transfer_piece(self, option: TransferOption) -> bool:
        '''尝试部件变换
        '''
        # 尝试放置变换后的部件
        new_piece = self.transfer_piece(option)
        if not self._board.is_piece_setable(new_piece):
            # 部件抵达
            if option in [TransferOption.LineDown, TransferOption.DropDown]:
                self.set_piece_arrived()
                self.update()
            return False
        # 更新部件
        self._curr_piece = new_piece
        # 刷新显示
        self._board.set_draw_piece(new_piece)
        self.update()
        return True

    def set_piece_arrived(self) -> None:
        '''部件抵达面板底部/触碰到累积部件方块
        ''' 
        # 更新面板
        self._board.set_occupy_piece(self._curr_piece)# 放置部件
        remove_lines = self._board.remove_full_lines()# 消除整行
        # 更新数据
        self.__data.update(remove_lines)
        self.__data.display()
        # 更新部件
        if not self.get_new_piece():
            return None
        # 更新显示
        if remove_lines:
            # self.set_timer_start(True, 500)# 更改定时事件, 等待移除界面刷新
            self._board.set_draw_piece(None)# 暂时不绘制新块
