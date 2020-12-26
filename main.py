import sys
from panel import Ui_MainWindow
from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtCore import Qt
from pyqt_led.pyqt_led import Led # From https://github.com/Neur1n/pyqt_led

import serial
import modbus_tk
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
import time

import os
import yaml
import time

class switch:
    def __init__(self, addr, port, master):
        self.addr = addr
        self.port = port
        self.master = master
        self.state = -1
        print("Init switch at {0} {1}".format(addr,port))
    def check_on(self):
        self.state = self.master.execute(self.addr, cst.READ_DISCRETE_INPUTS, self.port-1, 1)[0]
        return self.state

class motor:
    def __init__(self, addr, bridge, master):
        self.addr = addr
        self.bridge = bridge
        self.master = master
        (h1,h2,l1,l2) = bridge
        print("Init motor at {0} {1}".format(addr, bridge))
    def stop(self):
        res = self.master.execute(addr, cst.WRITE_SINGLE_COIL, h1-1, output_value=0)
        res = self.master.execute(addr, cst.WRITE_SINGLE_COIL, h2-1, output_value=0)
        res = self.master.execute(addr, cst.WRITE_SINGLE_COIL, l1-1, output_value=0)
        res = self.master.execute(io_port, cst.WRITE_SINGLE_COIL, l2-1, output_value=0)
        pass
    def forward(self):
        res = self.master.execute(addr, cst.WRITE_SINGLE_COIL, h1-1, output_value=1)
        res = self.master.execute(addr, cst.WRITE_SINGLE_COIL, h2-1, output_value=0)
        res = self.master.execute(addr, cst.WRITE_SINGLE_COIL, l1-1, output_value=0)
        res = self.master.execute(addr, cst.WRITE_SINGLE_COIL, l2-1, output_value=1)
        pass
    def reverse(self):
        res = self.master.execute(addr, cst.WRITE_SINGLE_COIL, h1-1, output_value=0)
        res = self.master.execute(addr, cst.WRITE_SINGLE_COIL, h2-1, output_value=1)
        res = self.master.execute(addr, cst.WRITE_SINGLE_COIL, l1-1, output_value=1)
        res = self.master.execute(addr, cst.WRITE_SINGLE_COIL, l2-1, output_value=0)
        pass

class entranceThread(QThread):
    updated = pyqtSignal(str)
    start_work = pyqtSignal(bool)
    def __init__(self):
        super(entranceThread, self).__init__()
        self.ser = None
        self.run_flag = False
    def setser(self, ser):
        self.ser = ser
        self.run_flag = True
        self.start()
    def threadStop(self):
        self.run_flag = False
    def run(self):
        print("Start Reading Entrance")
        self.run_flag = True
        while self.run_flag:
            try:
                if self.ser.in_waiting:
                    read_str=self.ser.read(self.ser.in_waiting )
                    # read_str=self.ser.read(self.ser.in_waiting ).hex()
                    self.updated.emit(str("[Read ] {}".format(read_str)))
                    if str(read_str,'utf-8').split("'")[0] == "ABCD":
                        self.start_work.emit(bool(True))
                    time.sleep(0.1) # CPU占用过高
            except Exception as e:
                print(str(e))

class workThread(QThread): # 主进程类
    updated = pyqtSignal(str)
    def __init__(self): # 初始化参数，全部为None
        super(workThread, self).__init__()  # 继承父类的初始化
        self.run_flag = False  # 主线程是否开启的标志falg，默认False（表示关闭）

        # 电机
        self.motor_D03 = None
        self.motor_D02 = None
        self.motor_D01 = None

        #开关
        self.switch_TDO1 = None
        self.switch_TD02 = None
        self.switch_D10 = None
        self.switch_TD08 = None
        self.switch_TD10 = None

    def setdevice(self, motor_D03, motor_D02, motor_D01, switch_TDO1, switch_TD02, switch_D10, switch_TD05, switch_TD06, switch_TD07, switch_TD08, switch_TD09, switch_TD10): # 设置参数，并开启线程
        # 电机
        self.motor_D03 = motor_D03
        self.motor_D02 = motor_D02
        self.motor_D01 = motor_D01

        #开关
        self.switch_TDO1 = switch_TDO1
        self.switch_TD02 = switch_TD02
        self.switch_D10  = switch_D10
        self.switch_TD08 = switch_TD08
        self.switch_TD09 = switch_TD09
        self.switch_TD10 = switch_TD10
        self.switch_TD05 = switch_TD05
        self.switch_TD06 = switch_TD06
        self.switch_TD07 = switch_TD07

        self.start()  # 启动主线程run()函数，线程开始工作
        self.run_flag = True # 线程开启，flag为True（表示开启）

    def threadStop(self):  # 结束线程
        self.run_flag = False # 线程结束，flag为False（表示关闭）
        print("Working thread died") # 主工作进程结束

    def run(self):
        print("Start Working thread")   
        while self.run_flag:
            try:
                self.switch_TDO1.check_on() # 检查开关TD01状态，关闭state=0，否则为1
                self.switch_TD02.check_on() # 检查开关TD02状态，关闭state=0，否则为1
                if self.switch_TDO1.state == 1 and self.switch_TD02.state == 1: # 如果开关TD01和TD02开启
                    time_start = time.time()  #开始计时
                    self.motor_D03.forward()   # 电机D03正转
                    self.switch_D10.state = 1 # 开关D10开启，state=1
                    self.switch_TD08.check_on() # 检查开关TD08状态
                    if self.switch_TD08.state == 0: # 如果开关TD08未触发
                        # 连续循环读五秒TD08状态，如果中途开启，state为并立即跳出循环，否则为0
                        time_TD08 = 0
                        while time_TD08 < 5:
                            time.sleep(1)
                            time_TD08 += 1
                            self.switch_TD08.check_on()
                            if self.state == 1:
                                break
                    if self.switch_TD08.state == 0: # 如果开关TD08五秒钟未触发
                        self.motor_D03.stop()   # 电机D03停止
                        pass # 报警（待写）
                    else:  # 开关TDO8开启
                        self.motor_D03.stop()   # 电机D03停止
                        self.switch_TD10.check_on() # 检查开关TD10状态
                        if self.switch_TD10.state == 1: # 如果开关TD10触发
                            pass # 称重（待写）D03
                        self.switch_TDO1.check_on() #检查TD01\TDO2的状态
                        self.switch_TD02.check_on()
                        time_flag = False#啥意思
                        if self.switch_TDO1.state == 1 or self.switch_TD02.state == 1: # 不满足皆不触发的条件
                            if self.switch_TDO1.state == 1 and self.switch_TD02.state == 1: # 如果皆触发
                                time_end = time.time()    #结束计时
                                time_c = time_end - time_start   #运行所花时间，单位s
                                if time_c > 60:
                                    time_flag = True
                                else:
                                    while time_c < 60:
                                        time.sleep(1)#休眠一秒
                                        time_c += 1
                                        self.switch_TDO1.check_on() 
                                        self.switch_TD02.check_on()
                                        if self.switch_TDO1.state == 0 and self.switch_TD02.state == 0:
                                            time_flag = True
                                            break
                                    time_flag = True
                        if time_flag = True:
                            self.motor_D03.reverse()  #D03电机反转
                            self.switch_D10.state = 0 # 开关D10关，state=0
                            #----上传投递信息
                            self.switch_TDO9.state = 1#TD09触发
                              if self.switch_TDO9.state == 1:#如果TD09触发
                                 self.motor_D03.stop() #D03电机停止

                                 self.switch_TDO5.check_on() #检查TD05\TDO6TD07的状态
                                 self.switch_TD06.check_on()
                                 self.switch_TD07.check_on()
                                  if self.switch_TDO5.check_on() == 0 and self.switch_TD06.check_on() == 0 and self.switch_TD07.check_on()==0:
                                        #等待下一个投递
                                    else:
                                        self.motor_D02.forward()
                                        self.switch_TDO11.state = 1
                                        if self.switch_TDO11.state == 1：
                                           self.motor_D02.stop()#
                                           self.motor_D01.forward()
                                           self.sw
                                           if 




                              else
                            time_start = time.time()  #开始计时
                            time_end = time.time()    #结束计时
                            time_c = time_end - time_start   #运行所花时间，单位s


                        

            except Exception as e:
                print(str(e))

    

class MyWindow(QtWidgets.QMainWindow,Ui_MainWindow):
    """
    init:
        set UI
        set led
        set self.serial_flag
        add serial_port item
        set logger
        set io_read/write_from,io_read/write_to 
    """
    def __init__(self):
        # set UI
        super(MyWindow,self).__init__() # 菱形继承
        self.setupUi(self)
        self.led_widget._layout = QtWidgets.QGridLayout(self.led_widget)
        self._create_leds()
        self._arrange_leds()
        for i in range (1,21):
            exec('self.serial_port.addItem("/dev/ttyS{0}")'.format(i))
        for i in range (1,21):
            exec('self.modbus_port.addItem("/dev/ttyS{0}")'.format(i))
        self.logger = modbus_tk.utils.create_logger("console")
        self.serial_flag = False

    #call after serial&master init
    def init_hardware(self):
        fileNamePath = os.path.split(os.path.realpath(__file__))[0]
        yamlPath = os.path.join(fileNamePath,'./config.yaml')
        config = None
        try:
            with open(yamlPath,'r',encoding='utf-8') as f:
                result = f.read()
                config = yaml.load(result,Loader=yaml.FullLoader)
                # init motor
                self.motor_1 = motor(config['digital_device']['addr'],tuple(config['digital_device']['output']['d01']), self.master)
                # init switches
                self.switch_1 = switch(config['digital_device']['addr'],config['digital_device']['input']['td01'], self.master)
        except Exception as e:
            self.serial_message.append("Read config at {} failed".format(yamlPath))
            print(x['digital_device']['addr'])

    """
    onclick:serial_connect
    input:
        self.serial_port.currentText()
        self.baud_rate.currentText()
        self.data_bit.currentText()
        self.parity.currentText()
        self.stop_bit.currentText()
    output:
        self.ser
        self.master
        self.serial_message
        self.serial_flag
    """
    def serial_connect(self):
        if not self.serial_flag:
            serial_port = self.serial_port.currentText()
            modbus_port = self.modbus_port.currentText()
            baud_rate = self.baud_rate.currentText()
            data_bit = int(self.data_bit.currentText())
            parity = self.parity.currentText()
            stop_bit = int(self.stop_bit.currentText())
            try:
                self.ser=serial.Serial(port=serial_port,baudrate=baud_rate,bytesize=data_bit,parity=parity,stopbits=stop_bit)
                self.mod=serial.Serial(port=modbus_port,baudrate=baud_rate,bytesize=data_bit,parity=parity,stopbits=stop_bit)
                self.master = modbus_rtu.RtuMaster(self.mod)
                self.master.set_timeout(0.5)
                self.master.set_verbose(True)
                self.logger.info("connected")
                if self.ser.isOpen():
                    self._serial_state("connected")
                    self.serial_message.append("[State] Seral connected")
                    self.serial_flag = True
                    self.init_hardware()
                    # Start entrance thread
                    self.entranceThread = entranceThread()
                    self.entranceThread.setser(self.ser)
                    self.entranceThread.updated.connect(self._thread_append)
                    self.entranceThread.start_work.connect(self._workthread)
            except Exception as e:
                self.serial_message.append("Open {0} failed, make sure you open the device".format(serial_port))
                self._serial_state("failed")
        else:
            self.serial_message.append("[State] Serial already connected")

    def serial_disconnect(self):
        try:
            self.ser.flush()
            if self.ser.isOpen():
                self.entranceThread.threadStop()
                self.entranceThread.quit()
                self.entranceThread = None

                self.master.close()
                self.ser.close()
                self._serial_state("wait")
                self.serial_message.append("[State] Serial disconnected")
            else:
                self._serial_state("failed")
                self.serial_message.append("[State] Serial can not connected")
            self.serial_flag = self.ser.isOpen()
        except Exception as e:
            self.serial_message.append("[State] Close serial connect failed")
            self._serial_state("wait")

    def _serial_state(self,state):
        if state == 'failed':
            self.waitinglabel.setStyleSheet("color:red;font-weight:bold")
            self.waitinglabel.setText("Failed")
        if state == 'wait':
            self.waitinglabel.setStyleSheet("color:black;font-weight:bold")
            self.waitinglabel.setText("Not Connected")
        if state == 'connected':
            self.waitinglabel.setStyleSheet("color:green;font-weight:bold")
            self.waitinglabel.setText("Connected")
        else:
            pass

    def clean_log(self):
        self.serial_message.clear()
        pass

    def _create_leds(self):
        for i in range (0,16):
            exec('self.led_widget.led_input{0} = Led(self.led_widget, on_color=Led.red, shape=Led.circle, build="debug")'.format(i))
        for i in range (0,16):
            exec('self.led_widget.led_output{0} = Led(self.led_widget, on_color=Led.red, shape=Led.circle, build="debug")'.format(i))
    
    def _arrange_leds(self):
        for i in range (0,16):
            exec('self.led_widget._layout.addWidget(self.led_widget.led_input{0},0,{0}, 1, 1, QtCore.Qt.AlignCenter)'.format(i))
        for i in range (0,16):
            exec('self.led_widget._layout.addWidget(self.led_widget.led_output{0},1,{0}, 1, 1, QtCore.Qt.AlignCenter)'.format(i))

    def _thread_append(self, text):
        self.serial_message.append(text)

    def _workthread(self, flag):
        if flag == True:
            self.workThread = workThread()
            self.workThread.setdevice(self.motor_1,self.switch_1)
            self.workThread.updated.connect(self._thread_append)
            pass

if __name__ == "__main__":
    QtWidgets.QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app=QtWidgets.QApplication(sys.argv)
    myshow=MyWindow()
    myshow.show()
    sys.exit(app.exec())