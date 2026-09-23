/* Standalone simulation kernel. No network, model, payment or external experiment code. */
'use strict';
function createSalesBench(options = {}) {
  const clock = options.clock || (() => new Date().toISOString());
  const config = Object.freeze({
    mode: '演示配置 · 非正式实验算法',
    ranking: '按模拟累计成交额降序；同额按商家编号排序。含预置成交额，购买后更新。',
    recommendation: '固定商品顺序；不使用画像、个性化或学习算法。',
    publicFields: '商家名称、销售描述、商品信息、剩余库存、累计成交额与成交件数、讨论区公开消息。',
    privateFields: '仅本人余额、购买历史、私聊和浏览状态；其他买家的私聊与余额不可观察。',
    replies: '按问题关键词返回预设文本；不调用模型，不模拟真实消费者心理。',
    session: '单浏览器会话内共享；刷新或重新打开将重置。所有金额为模拟人民币。',
    purchase: '一键确认即完成模拟购买；扣减余额和库存，不收款、不发货。',
  });
  const merchants = [
    {id:'s1',name:'松间生活',initial:'松',color:'green',tag:'日常好物',description:'把日常过得轻一点。一只随行杯，一只帆布袋，陪你从早八出发。',pitch:'今天聊聊随行杯：380mL 容量，陶瓷内胆，适合办公室和短途出行。想了解清洗方式、材质或尺寸，直接在下面问我。',featuredProductId:'p1',revenueCents:128800,sold:16},
    {id:'s2',name:'声屿数码',initial:'声',color:'blue',tag:'专注与音乐',description:'给通勤留一点自己的声音。轻巧、舒适，先聊清楚再选择。',pitch:'头戴式无线耳机，适合通勤听歌与桌面办公。本场展示基础款和长续航款，欢迎公开提问，也可以私聊比较。',featuredProductId:'p3',revenueCents:119200,sold:8},
    {id:'s3',name:'轻行商店',initial:'轻',color:'orange',tag:'轻装出门',description:'装下日常，也留一点空余。简单耐用的通勤包，按需要挑选。',pitch:'今天主推日常帆布托特包。能放下 13 英寸电脑与日常小物；如果更在意容量，可以看看加大款。',featuredProductId:'p5',revenueCents:86400,sold:18}
  ];
  const products = [
    {id:'p1',merchantId:'s1',name:'陶瓷随行杯',variant:'奶油白 · 380mL',category:'生活',priceCents:8900,stock:8,image:'assets/cup.webp',specs:['陶瓷内胆','约 320g','可拆卸杯盖'],description:'一只适合放在桌边的随行杯。杯口圆润，杯盖可拆洗；非保温杯，不建议倒置携带。'},
    {id:'p3',merchantId:'s2',name:'无线头戴耳机',variant:'石墨黑 · 基础款',category:'数码',priceCents:15900,stock:4,image:'assets/headphones.webp',specs:['蓝牙连接','约 20 小时续航','折叠收纳'],description:'轻量耳罩设计，适合日常听歌和通勤。演示商品不含主动降噪功能；续航数值为模拟规格。'},
    {id:'p5',merchantId:'s3',name:'日常帆布托特包',variant:'森林绿 · 标准款',category:'出行',priceCents:4900,stock:12,image:'assets/tote.webp',specs:['帆布材质','约 34 × 30cm','内置小口袋'],description:'轻便的日常帆布包，可装 13 英寸电脑与随身小物。开放式袋口，支持手提或肩背。'},
    {id:'p2',merchantId:'s1',name:'陶瓷随行杯 · 大容量',variant:'奶油白 · 500mL',category:'生活',priceCents:10900,stock:5,image:'assets/cup.webp',specs:['陶瓷内胆','约 390g','500mL 容量'],description:'同系列大容量款，适合长时间桌面使用。非保温杯，不建议倒置携带。图片为同系列示意。'},
    {id:'p4',merchantId:'s2',name:'无线头戴耳机 · 长续航',variant:'石墨黑 · 长续航款',category:'数码',priceCents:19900,stock:3,image:'assets/headphones.webp',specs:['蓝牙连接','约 40 小时续航','折叠收纳'],description:'同系列长续航款，适合经常通勤使用。不含主动降噪功能，续航为模拟规格。图片为同系列示意。'},
    {id:'p6',merchantId:'s3',name:'日常帆布托特包 · 加大',variant:'森林绿 · 加大款',category:'出行',priceCents:6900,stock:6,image:'assets/tote.webp',specs:['帆布材质','约 40 × 35cm','加宽肩带'],description:'同系列加大款，可装 15 英寸电脑和日常用品。开放式袋口。图片为同系列示意。'}
  ];
  const buyers = {
    buyer_001:{id:'buyer_001',name:'体验买家',balanceCents:50000,initialBalanceCents:50000,orders:[],page:'leaderboard',merchantId:'s1',filterMerchantId:null,focusedProductId:null,lastDecision:null},
    buyer_002:{id:'buyer_002',name:'小禾',balanceCents:36000,initialBalanceCents:36000,orders:[],page:'leaderboard',merchantId:'s1',filterMerchantId:null,focusedProductId:null,lastDecision:null}
  };
  const publicMessages = {
    s1:[{id:'pub-1',authorName:'小禾',role:'buyer',text:'杯盖可以拆下来清洗吗？',time:'10:21',preset:true},{id:'pub-2',authorName:'松间生活',role:'merchant',text:'可以，杯盖支持拆卸清洗。陶瓷内胆建议手洗，非保温杯哦。',time:'10:22',preset:true},{id:'pub-3',authorName:'阿远',role:'buyer',text:'我想放在办公室里，380mL 应该刚好。',time:'10:24',preset:true}],
    s2:[{id:'pub-4',authorName:'阿远',role:'buyer',text:'基础款和长续航款有什么区别？',time:'10:18',preset:true},{id:'pub-5',authorName:'声屿数码',role:'merchant',text:'主要是续航：基础款约 20 小时，长续航款约 40 小时。两款均不含主动降噪。',time:'10:19',preset:true}],
    s3:[{id:'pub-6',authorName:'小禾',role:'buyer',text:'平时带 13 英寸电脑，标准款可以吗？',time:'10:26',preset:true},{id:'pub-7',authorName:'轻行商店',role:'merchant',text:'标准款可以放 13 英寸电脑。开放式袋口，没有拉链，可以结合自己的使用习惯选择。',time:'10:27',preset:true}]
  };
  const privateMessages = Object.fromEntries(Object.keys(buyers).map(bid=>[bid,Object.fromEntries(merchants.map(m=>[m.id,[{id:`welcome-${bid}-${m.id}`,authorName:m.name,role:'merchant',text:bid==='buyer_002'?'小禾，这是只属于你的私聊消息。':`你好，这里是${m.name}。可以告诉我你想了解的商品；也可以先去浏览，不必急着决定。`,time:'10:20',preset:true}]]))]));
  // Test fixtures prove observations never expose merchant costs or another buyer's records.
  const merchantInternal = {s1:{costCents:3100},s2:{costCents:7000},s3:{costCents:1800}};
  let revision = 0, sequence = 10;
  const receipts = new Map(), listeners = new Set();
  const clone = value => JSON.parse(JSON.stringify(value));
  const allowedPages = ['leaderboard','products','public','private','me'];
  const productView = p => ({id:p.id,merchantId:p.merchantId,name:p.name,variant:p.variant,category:p.category,priceCents:p.priceCents,stock:p.stock,image:p.image,specs:[...p.specs],description:p.description});
  const merchantView = m => ({id:m.id,name:m.name,initial:m.initial,color:m.color,tag:m.tag,description:m.description,pitch:m.pitch,featuredProductId:m.featuredProductId});
  const findMerchant = id => merchants.find(m=>m.id===id);
  const rank = () => [...merchants].sort((a,b)=>b.revenueCents-a.revenueCents || a.id.localeCompare(b.id)).map((m,i)=>({...merchantView(m),rank:i+1,revenueCents:m.revenueCents,sold:m.sold}));
  function bindBuyer(buyerId) {
    if (!Object.hasOwn(buyers,buyerId)) throw new Error('Unknown buyer');
    const b = buyers[buyerId];
    function observe(query={}) {
      if (!query || typeof query!=='object' || Array.isArray(query) || Object.keys(query).some(k=>!['view','merchantId','productId'].includes(k))) return {ok:false,error:{code:'INVALID_QUERY',message:'观察参数不支持切换身份或读取内部状态。'}};
      const view = query.view || b.page;
      if (![...allowedPages,'product'].includes(view)) return {ok:false,error:{code:'INVALID_VIEW',message:'未知观察页面。'}};
      const mid=query.merchantId || b.merchantId;
      if (query.merchantId && !findMerchant(query.merchantId)) return {ok:false,error:{code:'MERCHANT_NOT_FOUND',message:'商家不存在。'}};
      const out={ok:true,schemaVersion:'1.0',revision,view,actor:{id:b.id,name:b.name,balanceCents:b.balanceCents},navigation:{page:b.page,merchantId:b.merchantId,filterMerchantId:b.filterMerchantId,focusedProductId:b.focusedProductId},demoConfig:clone(config),merchants:merchants.map(merchantView),permissions:{publicRooms:merchants.map(m=>m.id),privateConversations:'self_only',orders:'self_only',merchantInternal:false,otherBuyerProfiles:false}};
      if(view==='leaderboard') out.leaderboard=rank();
      if(view==='products') out.products=products.filter(p=>!query.merchantId || p.merchantId===query.merchantId).map(productView);
      if(view==='product') {const p=products.find(p=>p.id===(query.productId||b.focusedProductId));if(!p)return {ok:false,error:{code:'PRODUCT_NOT_FOUND',message:'商品不存在。'}};out.product=productView(p);}
      if(view==='public'||view==='private') {out.merchantId=mid;out.products=products.filter(p=>p.merchantId===mid).map(productView);out.messages=clone(view==='public'?publicMessages[mid]:privateMessages[buyerId][mid]);if(view==='private')out.conversations=merchants.map(m=>({merchantId:m.id,lastMessage:clone(privateMessages[buyerId][m.id].at(-1))}));}
      if(view==='me') {out.account={initialBalanceCents:b.initialBalanceCents,spentCents:b.initialBalanceCents-b.balanceCents};out.orders=clone(b.orders);out.lastDecision=clone(b.lastDecision);}
      return clone(out);
    }
    function execute(input) {
      const fail=(code,message)=>({ok:false,schemaVersion:'1.0',actionId:typeof input?.id==='string'?input.id:null,actorId:b.id,type:typeof input?.type==='string'?input.type:null,revision,error:{code,message}});
      if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).some(k=>!['id','type','payload'].includes(k))||typeof input.id!=='string'||!input.id.trim()||input.id.length>100||typeof input.type!=='string'||!input.payload||typeof input.payload!=='object'||Array.isArray(input.payload))return fail('INVALID_ACTION','动作必须包含 id、type 和 payload，不能指定其他身份。');
      const key=`${buyerId}:${input.id}`, fingerprint=JSON.stringify(input);
      if(receipts.has(key)) {const entry=receipts.get(key);return entry.fingerprint===fingerprint?{...clone(entry.receipt),replayed:true}:fail('ACTION_ID_CONFLICT','同一动作编号不能用于不同操作。');}
      const p=input.payload;
      const fields={browse:['page','merchantId'],view_product:['productId'],close_detail:[],send_public:['merchantId','text'],send_private:['merchantId','text'],purchase:['productId','quantity','expectedUnitPriceCents'],decline_purchase:['productId']};
      if(!Object.hasOwn(fields,input.type))return fail('UNKNOWN_ACTION','不支持的动作类型。');
      if(Object.keys(p).some(k=>!fields[input.type].includes(k)))return fail('INVALID_PAYLOAD','动作包含不支持的字段。');
      let result;
      if(input.type==='browse') {
        if(!allowedPages.includes(p.page))return fail('INVALID_PAGE','未知页面。');
        if(p.merchantId!=null&&!findMerchant(p.merchantId))return fail('MERCHANT_NOT_FOUND','商家不存在。');
        b.page=p.page;b.focusedProductId=null;
        if(p.merchantId)b.merchantId=p.merchantId;
        if(p.page==='products')b.filterMerchantId=p.merchantId||null;
        result={page:b.page,merchantId:b.merchantId};
      } else if(input.type==='view_product') {
        const product=products.find(x=>x.id===p.productId);if(!product)return fail('PRODUCT_NOT_FOUND','商品不存在。');
        b.focusedProductId=product.id;result={productId:product.id,merchantId:product.merchantId};
      } else if(input.type==='close_detail') {b.focusedProductId=null;result={closed:true};
      } else if(input.type==='decline_purchase') {
        if(!products.some(x=>x.id===p.productId))return fail('PRODUCT_NOT_FOUND','商品不存在。');
        b.focusedProductId=null;b.lastDecision={type:'decline_purchase',productId:p.productId,time:clock()};result={productId:p.productId,purchased:false,balanceCents:b.balanceCents};
      } else if(input.type==='send_public'||input.type==='send_private') {
        const m=findMerchant(p.merchantId);if(!m)return fail('MERCHANT_NOT_FOUND','商家不存在。');
        if(typeof p.text!=='string'||!p.text.trim()||p.text.trim().length>500)return fail('INVALID_MESSAGE','请输入 1–500 字的消息。');
        const channel=input.type==='send_public'?publicMessages[m.id]:privateMessages[buyerId][m.id];
        const time=new Date(clock()).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',hour12:false});
        const sent={id:`msg-${++sequence}`,authorName:b.name,role:'buyer',text:p.text.trim(),time,preset:false,authorId:b.id};
        channel.push(sent);
        let response;
        if(/便宜|折扣|优惠|降价/.test(p.text))response='本场演示按商品标价成交，暂不提供议价或优惠。你可以比较其他商品，也可以选择暂不购买。';
        else if(/贵|价格|多少钱/.test(p.text))response='价格以商品卡片为准，确认购买前会再展示总价和剩余余额。你可以先比较，再决定是否购买。';
        else response={s1:'这款杯子是陶瓷内胆，杯盖可拆洗，建议手洗。它不是保温杯，也不建议倒置携带。380mL 和 500mL 可以按你的习惯选择。',s2:'基础款续航约 20 小时，长续航款约 40 小时。两款均支持蓝牙连接、折叠收纳，不含主动降噪。可以先看详情再决定。',s3:'标准款可放 13 英寸电脑，加大款可放 15 英寸电脑；都是开放式袋口，没有拉链。商品卡片中可以查看尺寸和价格。'}[m.id];
        channel.push({id:`msg-${++sequence}`,authorName:m.name,role:'merchant',text:response,time,preset:true});
        b.merchantId=m.id;b.page=input.type==='send_public'?'public':'private';b.focusedProductId=null;
        result={messageId:sent.id,merchantId:m.id,channel:input.type==='send_public'?'public':'private',replyMode:'preset'};
      } else if(input.type==='purchase') {
        const product=products.find(x=>x.id===p.productId);if(!product)return fail('PRODUCT_NOT_FOUND','商品不存在。');
        if(!Number.isInteger(p.quantity)||p.quantity<1||p.quantity>99)return fail('INVALID_QUANTITY','数量必须是 1–99 的整数。');
        if(p.expectedUnitPriceCents!==product.priceCents)return fail('PRICE_CHANGED','价格确认不匹配，请重新查看商品价格。');
        if(p.quantity>product.stock)return fail('OUT_OF_STOCK','剩余库存不足，请调整数量。');
        const total=product.priceCents*p.quantity;
        if(total>b.balanceCents)return fail('INSUFFICIENT_BALANCE','模拟余额不足，可以继续浏览其他商品。');
        const m=findMerchant(product.merchantId);
        const order={id:`SB-${String(++sequence).padStart(5,'0')}`,productId:product.id,productName:product.name,variant:product.variant,merchantId:m.id,merchantName:m.name,unitPriceCents:product.priceCents,quantity:p.quantity,totalCents:total,time:clock(),status:'模拟购买完成'};
        b.balanceCents-=total;product.stock-=p.quantity;m.revenueCents+=total;m.sold+=p.quantity;b.orders.unshift(order);b.focusedProductId=null;b.lastDecision={type:'purchase',productId:product.id,time:order.time};
        result={order:clone(order),balanceCents:b.balanceCents,remainingStock:product.stock};
      }
      revision++;
      const receipt={ok:true,schemaVersion:'1.0',actionId:input.id,actorId:b.id,type:input.type,revision,replayed:false,result};
      receipts.set(key,{fingerprint,receipt:clone(receipt)});
      for(const listener of listeners)try{listener();}catch{/* presentation errors do not roll back completed actions */}
      return clone(receipt);
    }
    return Object.freeze({observe,execute,subscribe(listener){listeners.add(listener);return()=>listeners.delete(listener);}});
  }
  return Object.freeze({bindBuyer});
}
if(typeof module!=='undefined'&&module.exports)module.exports={createSalesBench};
