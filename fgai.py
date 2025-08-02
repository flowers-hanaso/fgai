# -*- coding: utf-8 -*-
from deepface import DeepFace
import cv2 as cv
import time, os, requests
import RPi.GPIO as GPIO
import subprocess

# Configuration
CAMERA_DEVICE     = 0 #カメラの番号
FACE_CASCADE_PATH = "path/to/cascade/model"
IMAGE_DIR         = "path/to/image/dilectry"

def send_line(picture, send_age):
    """画像付きでLINE通知"""
    #(情報保護のため省略)

def send_line_txt(txt):
    """テキストだけでLINE通知"""
    #(情報保護のため省略)

def door_check():
    """
    ドア状態のモック検出
    0 = 開扉中, 1 = 閉扉中
    """
    door_result = GPIO.input(4)
    return door_result

def door_close():
    if GPIO.input(4) == 0:
        """ドアを閉める動作"""
        print('閉扉動作を開始')
        while GPIO.input(4) == 0:
            #ドアクローザーの電源ON
            GPIO.output(17, True); GPIO.output(27, False); GPIO.output(22, True)
            time.sleep(0.1)
        print('閉扉動作を完了')
        GPIO.output(17, False); GPIO.output(27, True); GPIO.output(22, True)
        time.sleep(1)
        GPIO.output(17, False); GPIO.output(27, False); GPIO.output(22, False)
    else:
        print('すでに閉扉')

def reset_camera(camera_device):
    """カメラ接続をリセット"""
    cap = cv.VideoCapture(camera_device)
    cap.release()

def detect_faces(camera_device, cascade_path, img_no):
    """
    顔検出を 6 回試行し、検出ごとに画像を保存。
    Returns:
        face_count (int): 検出した顔の総数
        img_no     (int): 次の画像番号
    """
    face_count = 0
    cap = cv.VideoCapture(camera_device)
    if not cap.isOpened():
        print("カメラ起動でエラー発生")
        GPIO.output(25, False)
        GPIO.output(23, True)
        time.sleep(5)
        GPIO.output(23, False)
        return 0, img_no

    cap.set(cv.CAP_PROP_FRAME_WIDTH, 512)
    cap.set(cv.CAP_PROP_FRAME_HEIGHT, 384)

    for trial in range(6):
        ret, frame = cap.read()
        if not ret:
            print("キャプチャでエラーが発生")
            GPIO.output(25, False)
            GPIO.output(23, True)
            time.sleep(5)
            GPIO.output(23, False)
            time.sleep(0.2)
            continue

        grayimg = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        cascade = cv.CascadeClassifier(cascade_path)
        faces   = cascade.detectMultiScale(
            grayimg,
            scaleFactor=1.2,
            minNeighbors=5,
            minSize=(1, 1)
        )

        if len(faces) > 0:
            print('顔を検出')
            face_count += len(faces)
            save_path = os.path.join(IMAGE_DIR, f"{img_no}.jpg")
            cv.imwrite(save_path, frame)
            print(f'画像を保存：{save_path}')
            img_no += 1

        print(f"試行回数: {trial+1}/6")
        time.sleep(0.2)
        GPIO.output(24, False)
    GPIO.output(25, False)

    cap.release()
    return face_count, img_no

def estimate_age(image_path):
    """
    DeepFace で年齢推定を行い、結果の dict を返す。
    複数顔の場合は最初の結果を使用。
    """
    print('年齢の推測を開始')
    GPIO.output(25, True)
    time.sleep(0.2)
    GPIO.output(24, True)
    time.sleep(0.2)
    GPIO.output(23, True)
    img       = cv.imread(image_path)
    img_rgb   = cv.cvtColor(img, cv.COLOR_BGR2RGB)
    result    = DeepFace.analyze(img_rgb, actions=['age'], enforce_detection=False)
    if isinstance(result, list):
        result = result[0]
    GPIO.output(25, False)
    time.sleep(0.2)
    GPIO.output(24, False)
    time.sleep(0.2)
    GPIO.output(23, False)
    return result

def main():
    camera    = CAMERA_DEVICE
    cascade   = FACE_CASCADE_PATH
    img_no    = 0
    open_face = 0

    #GPIOセットアップ
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(17,GPIO.OUT)
    GPIO.setup(27,GPIO.OUT)
    GPIO.setup(22,GPIO.OUT)
    GPIO.setup(23,GPIO.OUT)
    GPIO.setup(24,GPIO.OUT)
    GPIO.setup(25,GPIO.OUT)
    GPIO.setup(4, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    GPIO.output(25, True)
    time.sleep(0.2)
    GPIO.output(24, True)
    time.sleep(0.2)
    GPIO.output(23, True)
    time.sleep(0.5)
    GPIO.output(25, False)
    time.sleep(0.2)
    GPIO.output(24, False)
    time.sleep(0.2)
    GPIO.output(23, False)

    # オンラインチェック
    try:
        proc   = subprocess.run(
            ['ping', '-c', '1', '8.8.8.8'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        online = (proc.returncode == 0)
    except Exception as e:
        print(f"Ping エラー: {e}")
        online = False

    if online:
        print('オンラインモードで開始')
        send_line_txt('オンラインモードで開始')
        GPIO.output(25, True)
        time.sleep(1)
        GPIO.output(25, False)
        online = 1
    else:
        print('オフラインモードで開始')
        GPIO.output(24, True)
        time.sleep(1)
        GPIO.output(24, False)
        online = 0


    while True:
        if door_check() == 0:
            print(f'開扉中 → 顔検出開始 (連続: {open_face})')
            face_count, img_no = detect_faces(camera, cascade, img_no)

            if face_count > 0:
                print('結果：顔は有り')
                open_face += 1
            else:
                if open_face > 0:
                    print('結果：顔が消失 → 閉扉 & 年齢判定へ')
                    door_close()
                    last_img_path = os.path.join(IMAGE_DIR, f"{img_no-1}.jpg")
                    if online:
                        analysis = estimate_age(last_img_path)
                        age_value = analysis.get('age')
                        print(f"推定年齢: {age_value}")
                        if age_value is not None and age_value >= 37:
                            send_line(last_img_path, '⚠️ 高齢者が冷蔵庫を開けたままにしたので閉扉しました ⚠️')
                    else:
                        print('(オフライン)')
                    open_face = 0
                else:
                    print('結果：顔は無し')
        else:
            print('閉扉中')
            open_face = 0

        time.sleep(1)

if __name__ == "__main__":
    try:
        print('AI冷蔵庫V410_起動完了')
        main()
    except KeyboardInterrupt:
        GPIO.cleanup()
        print("FINISH")
