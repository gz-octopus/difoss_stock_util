
    @classmethod
    def upsert(cls, new_record: _TSecurity, only_check=False) -> tuple[str ,Optional[_TSecurity]]:
        """检查该数据是(有差异则)插入还是(无差异则)更新(updated_at)

        Returns:
            如果数据有差异（需要 insert 新记录），则返回旧对象；
            否则，返回 None
        """
        session = cls.get_session()
        if new_record.updated_at is None:
            new_record.updated_at = datetime.now()

        try:
            code = SecurityCode((new_record.InstrumentID, new_record.ExchangeID))
            latest_record = cls._get_latest_by_code(session, code, new_record.updated_at) # type: _TSecurity
            if latest_record:
                if latest_record.updated_at >= new_record.updated_at:
                    # 数据库中数据的更新时间比 new_record 更加新鲜，无需修改
                    T("数据库的更新鲜，无需操作", _level='PASS',
                    stock=code.full_code, new=new_record.updated_at, updated_at=latest_record.updated_at) if cls._is_debug else None
                    return (None, latest_record)

                # 使用 == 运算符直接调用子类的 __eq__() 判断是否相等，可重载或重定义 __ignore_columns__ 来自定义比较规则。
                if latest_record == new_record: # new_record 数据更加新，但内容没变，只需更 DB.updated_at
                    I("更新 updated_at", _level='UPDATE', latest_record=latest_record) if cls._is_debug else None
                    if not only_check:
                        latest_record.update(updated_at = new_record.updated_at)
                        session.commit()
                        # session.refresh(latest_record)
                    return ('update', latest_record)
                else:
                    I("数据有变化，插入新记录", _level='INSERT', latest_record=latest_record) if cls._is_debug else None
                    if not only_check:
                        session.add(new_record)
                        session.commit()
                        session.refresh(new_record)
                    return ('insert', latest_record)
            else:
                if not only_check:
                    session.add(new_record)
                    session.commit()
                    session.refresh(new_record)
                I("首次插入记录", _level='NEW', new_record=new_record) if cls._is_debug else None
                return ('new', None)

        except Exception as e:
            session.rollback()
            print(f"操作数据时出错: {e}")
            import traceback
            traceback.print_exc()
            return ('error', None)
        finally:
            cls.close_session()