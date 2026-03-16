from typing import Callable, List, Tuple, Dict, Any
from functools import wraps
from alphaflow.core.schema.models import ResearchPack
from alphaflow.core.facade import ResearchPackFacade


class MetricEngine:
    """声明式基本面计算引擎 (V3 修订版：三元组精准注入)"""
    _registry: List[Dict[str, Any]] = []

    @classmethod
    def fundamental_metric(cls, feature_name: str, depends_on: List[Tuple[str, str, str]]):
        """
        高阶装饰器
        depends_on 格式: [("TTM", "income", "NET_INCOME"), ("LATEST", "balance", "TOTAL_EQUITY")]
        """
        def decorator(func: Callable):
            cls._registry.append({
                "feature_name": feature_name,
                "depends_on": depends_on,
                "func": func
            })
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    @classmethod
    def execute_all(cls, facade: ResearchPackFacade, pack: ResearchPack):
        """沙箱执行所有注册指标，自动防雷，自动写黑板"""
        for meta in cls._registry:
            try:
                args = []
                missing_data = False
                
                # 1. 自动依赖注入 (精准路由到特定报表)
                for period_type, domain, standard_key in meta["depends_on"]:
                    val = facade.resolve_dependency(period_type, domain, standard_key)
                    if val is None:
                        missing_data = True
                        break
                    args.append(val)
                
                # 如果底层数据缺失，静默跳过，绝不报错
                if missing_data:
                    continue
                
                # 2. 执行纯函数计算 (捕获除零等数学异常)
                result = meta["func"](*args)
                
                if result is not None:
                    # 3. 写入强类型输出槽位
                    pack.distilled_features.fundamental_metrics[meta["feature_name"]] = result
                    
                    # 4. 【核心魔法】自动向黑板宣告消费！屏蔽原始冗余字段！
                    for _, _, standard_key in meta["depends_on"]:
                        pack.registry.claim_standard_key(standard_key)
                        
            except Exception as e:
                print(f"  [MetricEngine] ⚠️ Error calculating {meta['feature_name']}: {e}")
