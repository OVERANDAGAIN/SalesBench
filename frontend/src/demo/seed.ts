// Data copied from the archived V1 prototype; demonstration fixtures only.
import type { Merchant, Product } from '../domain/types'

export const merchantSeeds: (Merchant & { revenueCents: number; sold: number })[] = [
    {id:'s1',name:'松间生活',initial:'松',color:'green',tag:'日常好物',description:'把日常过得轻一点。一只随行杯，一只帆布袋，陪你从早八出发。',pitch:'今天聊聊随行杯：380mL 容量，陶瓷内胆，适合办公室和短途出行。想了解清洗方式、材质或尺寸，直接在下面问我。',featuredProductId:'p1',revenueCents:128800,sold:16},
    {id:'s2',name:'声屿数码',initial:'声',color:'blue',tag:'专注与音乐',description:'给通勤留一点自己的声音。轻巧、舒适，先聊清楚再选择。',pitch:'头戴式无线耳机，适合通勤听歌与桌面办公。本场展示基础款和长续航款，欢迎公开提问，也可以私聊比较。',featuredProductId:'p3',revenueCents:119200,sold:8},
    {id:'s3',name:'轻行商店',initial:'轻',color:'orange',tag:'轻装出门',description:'装下日常，也留一点空余。简单耐用的通勤包，按需要挑选。',pitch:'今天主推日常帆布托特包。能放下 13 英寸电脑与日常小物；如果更在意容量，可以看看加大款。',featuredProductId:'p5',revenueCents:86400,sold:18}
  ]

export const productSeeds: Product[] = [
    {id:'p1',merchantId:'s1',name:'陶瓷随行杯',variant:'奶油白 · 380mL',category:'生活',priceCents:8900,stock:8,imageUrl:'/images/cup.webp',specs:['陶瓷内胆','约 320g','可拆卸杯盖'],description:'一只适合放在桌边的随行杯。杯口圆润，杯盖可拆洗；非保温杯，不建议倒置携带。'},
    {id:'p3',merchantId:'s2',name:'无线头戴耳机',variant:'石墨黑 · 基础款',category:'数码',priceCents:15900,stock:4,imageUrl:'/images/headphones.webp',specs:['蓝牙连接','约 20 小时续航','折叠收纳'],description:'轻量耳罩设计，适合日常听歌和通勤。演示商品不含主动降噪功能；续航数值为模拟规格。'},
    {id:'p5',merchantId:'s3',name:'日常帆布托特包',variant:'森林绿 · 标准款',category:'出行',priceCents:4900,stock:12,imageUrl:'/images/tote.webp',specs:['帆布材质','约 34 × 30cm','内置小口袋'],description:'轻便的日常帆布包，可装 13 英寸电脑与随身小物。开放式袋口，支持手提或肩背。'},
    {id:'p2',merchantId:'s1',name:'陶瓷随行杯 · 大容量',variant:'奶油白 · 500mL',category:'生活',priceCents:10900,stock:5,imageUrl:'/images/cup.webp',specs:['陶瓷内胆','约 390g','500mL 容量'],description:'同系列大容量款，适合长时间桌面使用。非保温杯，不建议倒置携带。图片为同系列示意。'},
    {id:'p4',merchantId:'s2',name:'无线头戴耳机 · 长续航',variant:'石墨黑 · 长续航款',category:'数码',priceCents:19900,stock:3,imageUrl:'/images/headphones.webp',specs:['蓝牙连接','约 40 小时续航','折叠收纳'],description:'同系列长续航款，适合经常通勤使用。不含主动降噪功能，续航为模拟规格。图片为同系列示意。'},
    {id:'p6',merchantId:'s3',name:'日常帆布托特包 · 加大',variant:'森林绿 · 加大款',category:'出行',priceCents:6900,stock:6,imageUrl:'/images/tote.webp',specs:['帆布材质','约 40 × 35cm','加宽肩带'],description:'同系列加大款，可装 15 英寸电脑和日常用品。开放式袋口。图片为同系列示意。'}
  ]

export const publicMessageSeeds = {
    s1:[{id:'pub-1',authorName:'小禾',role:'buyer',text:'杯盖可以拆下来清洗吗？',time:'10:21',preset:true},{id:'pub-2',authorName:'松间生活',role:'merchant',text:'可以，杯盖支持拆卸清洗。陶瓷内胆建议手洗，非保温杯哦。',time:'10:22',preset:true},{id:'pub-3',authorName:'阿远',role:'buyer',text:'我想放在办公室里，380mL 应该刚好。',time:'10:24',preset:true}],
    s2:[{id:'pub-4',authorName:'阿远',role:'buyer',text:'基础款和长续航款有什么区别？',time:'10:18',preset:true},{id:'pub-5',authorName:'声屿数码',role:'merchant',text:'主要是续航：基础款约 20 小时，长续航款约 40 小时。两款均不含主动降噪。',time:'10:19',preset:true}],
    s3:[{id:'pub-6',authorName:'小禾',role:'buyer',text:'平时带 13 英寸电脑，标准款可以吗？',time:'10:26',preset:true},{id:'pub-7',authorName:'轻行商店',role:'merchant',text:'标准款可以放 13 英寸电脑。开放式袋口，没有拉链，可以结合自己的使用习惯选择。',time:'10:27',preset:true}]
  }
