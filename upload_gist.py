# -*- coding: utf-8 -*-
import requests

html_code = """<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Share Lotto Result</title>
    <script src="https://static.line-scdn.net/liff/edge/2/sdk.js"></script>
</head>
<body style="background-color:#181A20; color:#FFFFFF; font-family:sans-serif; text-align:center; padding:50px 20px;">
    <h2 style="font-size:22px;">กำลังเปิดหน้าต่างแชร์ผลสลาก...</h2>
    <p style="color:#A0AAB8;">กรุณาเลือกกลุ่มหรือเพื่อนที่คุณต้องการส่งผลสลาก</p>

    <script>
        function createCleanFlex(name, top3, bottom2, flag) {
            var top3_fmt = top3.padStart(3, '0').slice(-3).split('').join('  ');
            var bottom2_fmt = bottom2.padStart(2, '0').slice(-2).split('').join('  ');

            return {
                "type": "bubble",
                "size": "mega",
                "header": {
                    "type": "box",
                    "layout": "horizontal",
                    "backgroundColor": "#1E222D",
                    "paddingAll": "lg",
                    "alignItems": "center",
                    "contents": [
                        { "type": "text", "text": flag, "size": "xl", "flex": 0 },
                        { "type": "text", "text": " " + name, "weight": "bold", "size": "xl", "color": "#FFFFFF", "flex": 1 }
                    ]
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#181A20",
                    "spacing": "md",
                    "paddingAll": "lg",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "vertical",
                            "backgroundColor": "#2A181A",
                            "cornerRadius": "md",
                            "paddingAll": "md",
                            "spacing": "xs",
                            "contents": [
                                { "type": "text", "text": "🔺 3 ตัวบน", "size": "sm", "color": "#FF6B6B", "weight": "bold" },
                                { "type": "text", "text": top3_fmt, "size": "3xl", "weight": "bold", "color": "#FF4D4D", "align": "center" }
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "backgroundColor": "#142438",
                            "cornerRadius": "md",
                            "paddingAll": "md",
                            "spacing": "xs",
                            "contents": [
                                { "type": "text", "text": "🔻 2 ตัวล่าง", "size": "sm", "color": "#4DABFF", "weight": "bold" },
                                { "type": "text", "text": bottom2_fmt, "size": "3xl", "weight": "bold", "color": "#00D2FF", "align": "center" }
                            ]
                        }
                    ]
                }
            };
        }

        async function main() {
            try {
                await liff.init({ liffId: '2011157640-izadxULb' });
                if (!liff.isLoggedIn()) {
                    liff.login();
                    return;
                }
                const urlParams = new URLSearchParams(window.location.search);
                const n = urlParams.get('n') || 'ผลสลาก';
                const t = urlParams.get('t') || '000';
                const b = urlParams.get('b') || '00';
                const f = urlParams.get('f') || '🎯';

                const flexObj = createCleanFlex(n, t, b, f);

                if (liff.isApiAvailable('shareTargetPicker')) {
                    await liff.shareTargetPicker([flexObj]);
                    liff.closeWindow();
                } else {
                    alert('อุปกรณ์นี้ไม่รองรับ Share Target Picker');
                    liff.closeWindow();
                }
            } catch (err) {
                console.error(err);
                liff.closeWindow();
            }
        }
        main();
    </script>
</body>
</html>
"""

def create_gist():
    payload = {
        "description": "LIFF share endpoint",
        "public": True,
        "files": {"share.html": {"content": html_code}},
    }
    r = requests.post("https://api.github.com/gists", json=payload)
    raw_url = r.json()["files"]["share.html"]["raw_url"]
    cdn_url = raw_url.replace("https://gist.githubusercontent.com/", "https://raw.githack.com/")
    print("Gist raw.githack URL:", cdn_url)
    return cdn_url

if __name__ == "__main__":
    create_gist()
