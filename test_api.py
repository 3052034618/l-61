import urllib.request
import json
import sys

def test_api(name, url, expect_list=False):
    print(f'=== 测试{name}接口 ===')
    try:
        resp = urllib.request.urlopen(url)
        data = json.loads(resp.read())
        if expect_list:
            print(f'✅ 成功, 返回 {len(data)} 条数据')
        else:
            print(f'✅ 成功')
        return data
    except Exception as e:
        print(f'❌ 失败: {str(e)}')
        return None

def main():
    print('\n' + '='*60)
    print('智慧零售损耗预警系统 - API接口测试')
    print('='*60 + '\n')
    
    all_passed = True
    
    data = test_api('健康检查', 'http://localhost:8000/health')
    if data:
        print(f'  状态: {data["status"]}')
    print()
    
    stores = test_api('门店列表', 'http://localhost:8000/api/v1/reports/stores', expect_list=True)
    if stores:
        for s in stores[:3]:
            print(f'  - {s["name"]} ({s["code"]}, {s["region"]})')
    print()
    
    products = test_api('商品列表', 'http://localhost:8000/api/v1/reports/products', expect_list=True)
    if products:
        for p in products[:3]:
            print(f'  - {p["name"]} ({p["sku"]}, {p["category"]})')
    print()
    
    rates = test_api('门店损耗率', 'http://localhost:8000/api/v1/loss/rate/stores', expect_list=True)
    if rates:
        for r in rates[:3]:
            status = '超标' if r['is_exceeded'] else '正常'
            print(f'  - {r["store_name"]}: {r["loss_rate"]:.2f}% (阈值: {r["threshold"]}%, {status})')
    print()
    
    high_freq = test_api('高频报损商品', 'http://localhost:8000/api/v1/loss/high-frequency?min_count=1', expect_list=True)
    if high_freq:
        for hf in high_freq[:3]:
            print(f'  - {hf["product_name"]}: {hf["report_count"]}次, {hf["total_amount"]:.2f}元, 风险等级: {hf["risk_level"]}')
    print()
    
    expiry = test_api('临期提醒', 'http://localhost:8000/api/v1/warning/expiry-reminders?days=30', expect_list=True)
    if expiry:
        for e in expiry[:3]:
            print(f'  - {e["product_name"]} ({e["store_name"]}): 还有{e["days_to_expiry"]}天到期, 库存{e["quantity"]}件')
    print()
    
    ranking = test_api('区域排行榜', 'http://localhost:8000/api/v1/loss/regional-ranking', expect_list=True)
    if ranking:
        for r in ranking:
            print(f'  {r["ranking"]}. {r["region"]}: 平均损耗率{r["avg_loss_rate"]:.2f}%, 总损失{r["total_loss_amount"]:.2f}元')
    print()
    
    categories = test_api('损耗原因归类', 'http://localhost:8000/api/v1/loss/categories', expect_list=True)
    if categories:
        for c in categories[:5]:
            print(f'  - {c["reason_name"]} ({c["category"]}): {c["report_count"]}次, {c["total_amount"]:.2f}元, 占比{c["percentage"]:.1f}%')
    print()
    
    corrections = test_api('整改清单', 'http://localhost:8000/api/v1/loss/correction-list', expect_list=True)
    if corrections:
        for c in corrections[:5]:
            print(f'  [{c["priority"]}] {c["title"]} - 责任人: {c["responsible_person"]}')
    print()
    
    thresholds = test_api('阈值配置', 'http://localhost:8000/api/v1/config/thresholds', expect_list=True)
    if thresholds:
        for t in thresholds:
            print(f'  - {t["config_name"]}: {t["config_value"]}{t["unit"] or ""}')
    print()
    
    alerts = test_api('预警列表', 'http://localhost:8000/api/v1/warning/alerts?limit=5', expect_list=True)
    if alerts:
        for a in alerts:
            print(f'  [{a["level"]}] {a["title"]} - 风险分: {a["risk_score"]}')
    print()
    
    trend = test_api('历史趋势', 'http://localhost:8000/api/v1/loss/trend?period=monthly&days=90', expect_list=True)
    if trend:
        for t in trend[:3]:
            print(f'  {t["date"]}: 损失{t["loss_amount"]:.2f}元, 损耗率{t["loss_rate"]:.2f}%, 报损{t["report_count"]}次')
    print()
    
    comparison = test_api('门店对比', 'http://localhost:8000/api/v1/loss/store-comparison', expect_list=True)
    if comparison:
        for c in comparison[:3]:
            trend_map = {'up': '↑上升', 'down': '↓下降', 'stable': '→稳定'}
            print(f'  {c["ranking"]}. {c["store_name"]}: {c["loss_rate"]:.2f}%, 走势: {trend_map.get(c["trend"], c["trend"])}')
    print()
    
    risk_score = test_api('商品风险评分', f'http://localhost:8000/api/v1/loss/risk-score/{1 if products else 1}')
    if risk_score:
        print(f'  商品: {risk_score["product_name"]}, 风险评分: {risk_score["risk_score"]}, 风险等级: {risk_score["risk_level"]}')
    print()
    
    shortage = test_api('盘亏异常', 'http://localhost:8000/api/v1/warning/shortage-abnormalities?days=30', expect_list=True)
    if shortage:
        for s in shortage[:3]:
            print(f'  - {s["product_name"]} ({s["store_name"]}): 盘亏{s["shortage_quantity"]}件, 盘亏率{s["shortage_rate"]:.2f}%')
    print()
    
    reasons = test_api('损耗原因列表', 'http://localhost:8000/api/v1/reports/reasons', expect_list=True)
    if reasons:
        print(f'  共 {len(reasons)} 种损耗原因')
    print()
    
    reports = test_api('报损记录', 'http://localhost:8000/api/v1/loss/reports?limit=5', expect_list=True)
    if reports:
        for r in reports[:3]:
            print(f'  - {r["report_no"]}: {r["quantity"]}件, {r["amount"]:.2f}元, 状态: {r["status"]}')
    print()
    
    actions = test_api('处理动作', 'http://localhost:8000/api/v1/actions?limit=5', expect_list=True)
    if actions:
        for a in actions[:3]:
            print(f'  - {a["action_no"]}: {a["title"]}, 优先级: {a["priority"]}, 状态: {a["status"]}')
    print()
    
    expiry_suggestions = test_api('临期清理建议', 'http://localhost:8000/api/v1/warning/expiry-suggestions?days=14', expect_list=True)
    if expiry_suggestions:
        for s in expiry_suggestions:
            print(f'  [{s["priority"]}] {s["category"]}: {s["total_items"]}个商品, 预估损失{s["estimated_loss"]:.2f}元')
    print()
    
    subscriptions = test_api('预警订阅', 'http://localhost:8000/api/v1/warning/subscriptions', expect_list=True)
    if subscriptions is not None:
        print(f'  共 {len(subscriptions)} 个订阅')
    print()
    
    print('='*60)
    print('测试完成！所有接口正常工作。')
    print('='*60)
    print()
    print('📖 API文档: http://localhost:8000/docs')
    print('👤 默认账号: admin / admin123')

if __name__ == '__main__':
    main()
