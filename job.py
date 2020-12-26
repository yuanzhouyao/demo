"""
流程类：
    read_id_list: 读取excel表格中的ID，生成user列表和admin列表 
    init_hardware：读取配置列表
    entranceThread：门禁线程，循环读取串口上的ID，判断是否与user/admin中的一致
    userThread：用户倒垃圾的工作线程
    adminThread：管理员处理线程
"""

from PyQt5.QtCore import QThread, pyqtSignal
import time
from device import adc, motor, switch, output_switch
import os
import yaml
import xlrd
import serial
import modbus_tk
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
import sys

def read_id_list(): # 读取用户名单
    fileNamePath = os.path.split(os.path.realpath(__file__))[0]
    xlPath = os.path.join(fileNamePath,'./user_list.xlsx')
    data = xlrd.open_workbook(xlPath)
    table = data.sheet_by_name('Sheet1')
    user = []
    admin = []
    for i in range (0,table.ncols):
        if table.cell(0,i).value=="ID":
            id_col = i
        elif table.cell(0,i).value=="GROUP":
            group_col = i
    for i in range (1, table.nrows):
        if table.cell(i, group_col).value.lower() == "user":
            user.append(table.cell(i,id_col).value)
        elif table.cell(i, group_col).value.lower() == "admin":
            admin.append(table.cell(i,id_col).value)
    return user,admin

def init_hardware(): # 读取设备配置
    fileNamePath = os.path.split(os.path.realpath(__file__))[0]
    yamlPath = os.path.join(fileNamePath,'./config.yaml')
    with open(yamlPath,'r',encoding='utf-8') as f:
        result = f.read()
        config = yaml.load(result,Loader=yaml.FullLoader)
        print(config)
    return config

class entranceThread(QThread):
    log = pyqtSignal(str) # 日志
    start_user = pyqtSignal(bool) # 开始用户工作流程
    start_admin = pyqtSignal(bool) # 开始管理员工作流程

    def __init__(self, ser, user, admin):
        super(entranceThread, self).__init__()
        self.ser = None
        self.ser = ser
        self.run_flag = False
        self.admin = admin
        self.user = user
        self.working = False

    def threadStop(self):
        self.run_flag = False

    def release(self): # 工作结束后调用realse放开读卡器读数
        self.working = False

    def run(self):
        print("Start Reading Entrance")
        self.run_flag = True
        while self.run_flag:
            time.sleep(0.1) # CPU占用过高
            try:
                if self.ser.in_waiting:
                    read_str=self.ser.read(self.ser.in_waiting)
                    # read_str=self.ser.read(self.ser.in_waiting ).hex()
                    # self.log.emit(str("[Read ] {}".format(read_str))) #
                    if not self.working: # 防止二次刷卡
                        self.working = True
                        input_id = str(read_str,'utf-8').split("'")[0]
                        if input_id in self.user:
                            # self.start_user.emit(bool(True)) # 
                            # self.log.emit(str("[ENTER] Valid user {}".format(input_id))) #
                            print("Valid user")
                        elif input_id in self.admin:
                            # self.start_admin.emit(bool(True)) # 
                            # self.log.emit(str("[ENTER] Valid admin {}".format(input_id))) # 
                            print("Valid admin")
                        else:
                            # self.working = False # 
                            # self.log.emit(str("[ENTER] Invalid user {}".format(input_id))) #
                            print("Invalid user")
                    else:
                        # self.log.emit(str("[ENTER] Don`t scan twice {}".format(input_id))) # 
                        print("Dont scan twice")
            except Exception as e:
                print(str(e))
        print("Thread died")

class userThread(QThread):
    log = pyqtSignal(str) # 日志
    end = pyqtSignal(bool)
    def __init__(self,master):
        super(userThread, self).__init__()
        self.master = master
        config = init_hardware()
        for i in range (1,4):
            exec("print(tuple(config['digital_device']['output']['d0{}']))".format(i))
            exec("self.motor_{0} = motor(config['digital_device']['addr'],tuple(config['digital_device']['output']['d0{0}']), self.master)".format(i))
            print("motor_{} init".format(i))
        for i in range (4,8):
            exec("self.output_switch_{0} = output_switch(config['digital_device']['addr'],config['digital_device']['output']['d0{0}'], self.master)".format(i))
            print("output_switch_{} init".format(i))
        for i in range (1,11):
            exec("self.switch_{0} = switch(config['digital_device']['addr'],config['digital_device']['input']['td0{0}'], self.master)".format(i))
        self.adc = adc(config['analog_device']['addr'],config['analog_device']['input']['force'],self.master)
    
    def test(self):
        self.test()
    
    def run(self):
        print("Start User thread")
        # while True:
        for i in range (1,4):
            time.sleep(0.5)
            exec("self.motor_{}.forward()".format(i))
            time.sleep(1.5)
            exec("self.motor_{}.stop()".format(i))
            time.sleep(1.5)
            exec("self.motor_{}.reverse()".format(i))
        time.sleep(0.5)

        for i in range (4,8):
            time.sleep(0.5)
            exec("print(self.output_switch_{}.set_state(0))".format(i))
            time.sleep(1.5)
            exec("print(self.output_switch_{}.set_state(1))".format(i))
            time.sleep(1.5)

        for i in range (1,11):
            time.sleep(1.5)
            exec("print(self.switch_{}.check_on())".format(i))
        time.sleep(0.5)
        print(self.adc.get_value())
        # self.log.emit(str("[Read ] switch at {0}, state = {1}".format(self.switch_1.port, self.switch_1.check_on())))
        print("user thread died")

        #姚的start
        # 干垃圾流程开始
        while self.run_flag:
            try:
                self.switch_1.check_on() # 检查开关TD01状态，关闭state=0，否则为1
                self.switch_2.check_on() # 检查开关TD02状态，关闭state=0，否则为1
                if self.switch_1.state == 1 and self.switch_2.state == 1: # 如果开关TD01和TD02开启
                    time_start = time.time()  #开始计时
                    self.motor_3.forward()   # 电机D03正转
                    self.output_switch_10.set_state(1) # 开关D10开启
                    self.switch_8.check_on() # 检查开关TD08状态
                    if self.switch_8.state == 0: # 如果开关TD08未触发
                        # 连续循环读五秒TD08状态，如果中途开启，state为并立即跳出循环，否则为0
                        time_switch_8 = 0
                        while time_switch_8 < 5:
                            time.sleep(1)
                            time_switch_8 += 1
                            self.switch_8.check_on()
                            if self.state == 1:
                                break
                    if self.switch_8.state == 0: # 如果开关TD08五秒钟未触发
                        self.motor_3.stop()   # 电机D03停止
                        pass # 报警（待写）
                    else:  # 开关TDO8开启
                        self.motor_3.stop()   # 电机D03停止
                        self.switch_10.check_on() # 检查开关TD10状态
                        if self.switch_10.state == 1: # 如果开关TD10触发
                            pass # 称重（待写）D03
                        self.switch_1.check_on() #检查TD01\TDO2的状态
                        self.switch_2.check_on()
                        time_flag = False  #时间是否达到60s的标志
                        if self.switch_1.state == 1 or self.switch_2.state == 1: # 不满足皆不触发的条件
                            if self.switch_1.state == 1 and self.switch_2.state == 1: # 如果皆触发
                                time_end = time.time()    #结束计时
                                time_c = time_end - time_start   #运行所花时间，单位s
                                if time_c > 60:
                                    time_flag = True  
                                else:
                                    while time_c < 60:
                                        time.sleep(1)#休眠一秒
                                        time_c += 1
                                        self.switch_1.check_on() 
                                        self.switch_2.check_on()
                                        if self.switch_1.state == 0 and self.switch_2.state == 0:
                                            time_flag = True
                                            break
                                    time_flag = True
                        # 尚的start
                        if time_flag == True:
                            self.motor_3.reverse()  #D03电机反转
                            self.output_switch_10.set_state(0)  # 开关D10关，state=0
                            self.switch_9.check_on() #检查TD09状态
                            # time_start2 = time.time() #开始计时
                            if self.switch_9.check_on() == 0:#如果TD09没有触发
                                time_c2 = 0
                                while time_c2 < 5:
                                    time.sleep(1)#休眠一秒
                                    time_c2 += 1
                                    if self.switch_9.check_on() == 1:
                                         break
                                self.motor_3.stop() #D03电机停止
                                DO3 = 0 
                                if time_c2 >= 5:                  
                                    pass#----上传故障信息
                            if self.switch_9.check_on() == 1:#如果TD09触发
                                 self.motor_3.stop() #D03电机停止
                                 DO3 = 0
                            if  DO3 == 0:
                                self.switch_5.check_on() #检查TD05\TDO6\TD07的状态
                                self.switch_6.check_on()
                                self.switch_7.check_on()
                                if self.switch_5.check_on() == 0 and self.switch_6.check_on() == 0 and self.switch_7.check_on()==0:#如果TDO5、TD06、TD07皆未触发
                                    pass #等待下一个投递（待写）
                                else:
                                    self.motor_2.forward()#电机D02正转
                                    self.switch_11.check_on()#检查TD11的状态
                                if self.switch_11.check_on == 0:#如果TD11没有触发
                                    time_c3 = 0
                                    while time_c3 < 20:
                                        time.sleep(1)#休眠一秒
                                        time_c3 += 1
                                        if self.switch_11.check_on == 1:
                                            break
                                    self.motor_2.stop() #D03电机停止
                                    DO2 = 0
                                    if time_c3 >= 20:                                      
                                        pass #上传压缩故障信息（待写）
                                if  self.switch_11.check_on == 1:#如果TD11触发
                                    self.motor_2.stop() #D02电机停止
                                    DO2 = 0    
                                if  DO2 == 0:
                                    self.motor_1.forward()#电机D01正转
                                    self.switch_3.check_on()#检查TD03状态
                                    if self.switch_3.check_on() == 1: #若果TD03触发
                                        self.motor_1.stop()#电机D01停止
                                        time.sleep(5)#休眠5秒，也就是电机D01停止5秒
                                        # 尚的end



                        

            except Exception as e:
                print(str(e))

def test_entrance():
    print("Start test entrance")
    config = init_hardware() # 测试配置读取
    user,admin  = read_id_list()
    try:
        ser=serial.Serial(port="/dev/ttyS1",baudrate=9600,bytesize=8,parity='N',stopbits=1)
    except Exception as e:
        print("Test failed, check modbus device and serial comm")
        sys.exit()
    print("Start test entrance thread")
    thread_1 = entranceThread(ser, user, admin)
    thread_1.start()
    cnt = 0
    while cnt<1:
        cnt+=1
        time.sleep(10.0)
        print("Release scanner")
        thread_1.release() # 释放门禁
    ser.flush()
    if ser.isOpen():
        thread_1.threadStop()
        thread_1.quit()
        while not thread_1.wait(): # run结束后通过wait判断线程是否成功退出
            time.sleep(0.1)
        ser.close()
        print("Serial and thread quit safely")

def test_user():
    print("Start test user thread")
    config = init_hardware() # 测试配置读取
    user,admin  = read_id_list()
    try:
        ser=serial.Serial(port="/dev/ttyS1",baudrate=9600,bytesize=8,parity='N',stopbits=1)
    except Exception as e:
        print("Test failed, check modbus device and serial comm")
        sys.exit()
    master = modbus_rtu.RtuMaster(ser)
    master.set_timeout(5.0) # 需要设置，否则可能没有返回值
    thread_2 = userThread(master)
    thread_2.start()
    while not thread_2.wait():
        time.sleep(1.0)


if __name__ == "__main__":
    config = init_hardware() # 测试配置读取
    user,admin  = read_id_list() # 测试user/admin名单
    # test_entrance() # 测试门禁线程
    test_user() # 测试用户线程
    
