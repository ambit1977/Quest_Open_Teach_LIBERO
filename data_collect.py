import hydra
from openteach.components import Collector

@hydra.main(version_base = '1.2', config_path = 'configs', config_name = 'collect_data')
def main(configs):
    collector = Collector(configs, configs.demo_num)
    processes = collector.get_processes()

    try:
        for process in processes:
            process.start()

        for process in processes:
            process.join()
    except KeyboardInterrupt:
        print("Stopping data collection processes...")
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
        for process in processes:
            if process.pid is not None:
                process.join(timeout=5)

if __name__ == '__main__':
    main()
