#!/bin/bash

# Configuration
POST_ID=1824
WEEKS=(9 10 11 12)
DAYS=("Monday" "Tuesday" "Wednesday" "Thursday" "Friday" "Saturday" "Sunday")
OUTPUT_DIR="data"

mkdir -p "$OUTPUT_DIR"

for week in "${WEEKS[@]}"; do
    week_index=$((week - 1))
    for day in "${DAYS[@]}"; do
        echo "Downloading Week $week, $day..."

        padded_week=$(printf "%02d" "$week")
        filename="$OUTPUT_DIR/streek-wk$padded_week-$day.json"

        curl 'https://app.streek.run/wp-admin/admin-ajax.php' \
            -X 'POST' \
            -H 'Content-Type: application/x-www-form-urlencoded' \
            -H 'Pragma: no-cache' \
            -H 'Accept: */*' \
            -H 'Sec-Fetch-Site: same-origin' \
            -H 'Accept-Language: en-AU,en;q=0.9' \
            -H 'Cache-Control: no-cache' \
            -H 'Sec-Fetch-Mode: cors' \
            -H 'Accept-Encoding: gzip, deflate, br' \
            -H 'Origin: https://app.streek.run' \
            -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15' \
            -H "Referer: https://app.streek.run/training-plan/base-training-plan/?week=$week&day=$day" \
            -H 'Sec-Fetch-Dest: empty' \
            -H 'Cookie: wordpress_sec_08d5f242764963abcd3f7f37b5c48054=hstreek%40umai.blue%7C1768187913%7CHoaImzaWbllXtF3pzzfyEKWDV60LP3Emk8f84mSmk8P%7C45ddf8267e723609ab705d7331b909139d67a960afdd507f3074903522784467; _fbp=fb.1.1763277835697.816506089998192683; _ga_WD8RM8XRC8=GS2.1.s1767323209$o25$g1$t1767324290$j60$l0$h0; __cf_bm=_qQsLY6346auMO76XlO7RLGK5P.CCZa5gb46D8BlV5M-1767324289-1.0.1.1-CLWxW9Vvb_DBqcD1adfA7bpzEUoYDUXzgMs0WGqVBut4wmLqetwXiFKWQlniv1EGxhwyzUEHhyMm0VPbVs79YtyqvaH7zor6z83GF0vL3PA; _ga=GA1.1.184767984.1763277829; cf_clearance=0NFWDUU1yf_Xsr1QON.aLStQp5nEuHvPpve7XhBk1so-1767324289-1.2.1.1-a3PcSNiQoToC_kcTlUcoYIw9Ls7xRt1058IcaLnF03zLu9XgDSdmLVAJIyEQGDrdERxRu6pc0Vvlmnvj4KRAHjOiV2Pa5JEM0yxc7TDC1.UX1eEB14xKJL_XcicSmojA.TKTESiIFjyD.oPeGcYJeFCgPaH9TGJmo1Bk49qGUBVZJweXJ3wDcttQCcZLLvKOjAaDKJ0vdU.PEGvEX1l7C7vch4RKgq2dXmQx5y1JHxk; wordpress_logged_in_08d5f242764963abcd3f7f37b5c48054=hstreek%40umai.blue%7C1768187913%7CHoaImzaWbllXtF3pzzfyEKWDV60LP3Emk8f84mSmk8P%7Ce9eb55a5ac73979b487a849b5f46b657097f4ae4c8d16390648aa6b546afbb4f; _ga_X5XX0TQSVK=GS2.1.s1763277828$o1$g0$t1763277828$j60$l0$h0; cookieyes-consent=consentid:aVA0M2ttcWJVNW94NlZkTlNTcExNdXdDMndGbzFmYjg,consent:no,action:,necessary:yes,functional:no,analytics:no,performance:no,advertisement:no,other:no; __stripe_mid=13edaca6-1fff-4fdf-aefe-34f517901e8b50d69b; cookieyes-consent=consentid:RDVUdlZhT3B4MXhzWnF3bkc2c3RmUTluR2VvMFl0Ukk,consent:yes,action:no,necessary:yes,functional:yes,analytics:yes,performance:yes,advertisement:yes,other:yes' \
            -H 'X-Requested-With: XMLHttpRequest' \
            -H 'Priority: u=3, i' \
            --data-urlencode "action=set_day_name" \
            --data-urlencode "dayName=$day" \
            --data-urlencode "postId=$POST_ID" \
            --data-urlencode "weekIndex=$week_index" \
            --compressed \
            -o "$filename"

        sleep 1 # Be nice to the server
    done
done

echo "Done! Workouts saved to $OUTPUT_DIR"

